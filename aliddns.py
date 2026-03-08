# -*- coding: utf-8 -*-
import json
import logging
import time
import random
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkalidns.request.v20150109.DescribeSubDomainRecordsRequest import DescribeSubDomainRecordsRequest
from aliyunsdkalidns.request.v20150109.UpdateDomainRecordRequest import UpdateDomainRecordRequest
from aliyunsdkalidns.request.v20150109.AddDomainRecordRequest import AddDomainRecordRequest
from aliyunsdkalidns.request.v20150109.DeleteSubDomainRecordsRequest import DeleteSubDomainRecordsRequest

# Configuration variables (overridden by config file and CLI args)
CONFIG = {
    'ipv4_enabled': True,
    'ipv6_enabled': True,
    'access_key_id': "",
    'access_secret': "",
    'domain': "",
    'ipv4_prefix': "mint",
    'ipv6_prefix': "mint6",
    'retry_attempts': 2,
    'retry_delay': 1,
    'request_timeout': 8,
    'log_file': '/tmp/aliddns.log'  # Default fallback log file
}

def load_config():
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Aliyun DDNS Updater CLI")
    parser.add_argument("-c", "--config", default=os.path.expanduser("~/.config/aliddns/config.json"), help="Path to config file (default: ~/.config/aliddns/config.json)")
    parser.add_argument("--access-key-id", help="Aliyun AccessKey ID")
    parser.add_argument("--access-secret", help="Aliyun AccessKey Secret")
    parser.add_argument("--domain", help="Main domain (e.g. med129.com)")
    parser.add_argument("--ipv4-prefix", help="IPv4 subdomain prefix")
    parser.add_argument("--ipv6-prefix", help="IPv6 subdomain prefix")
    parser.add_argument("--disable-ipv4", action="store_true", help="Disable IPv4 updating")
    parser.add_argument("--disable-ipv6", action="store_true", help="Disable IPv6 updating")
    
    args = parser.parse_args()
    
    # 1. Load from file if exists
    if os.path.exists(args.config):
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                CONFIG.update(file_config)
        except Exception as e:
            print(f"Error loading config file {args.config}: {e}")
            
    # 2. Override with CLI arguments (highest priority)
    if args.access_key_id: CONFIG['access_key_id'] = args.access_key_id
    if args.access_secret: CONFIG['access_secret'] = args.access_secret
    if args.domain: CONFIG['domain'] = args.domain
    if args.ipv4_prefix: CONFIG['ipv4_prefix'] = args.ipv4_prefix
    if args.ipv6_prefix: CONFIG['ipv6_prefix'] = args.ipv6_prefix
    if args.disable_ipv4: CONFIG['ipv4_enabled'] = False
    if args.disable_ipv6: CONFIG['ipv6_enabled'] = False
    
    # Validation
    if not CONFIG['access_key_id'] or not CONFIG['access_secret'] or not CONFIG['domain']:
        parser.error("Missing required configuration: access_key_id, access_secret, and domain must be provided via config file or CLI arguments.")

# IPv4 IP获取服务列表（根据日志表现重新排序，移除不稳定的服务）
IPV4_SERVICES = [
    {
        'url': 'https://httpbin.org/ip',
        'name': 'httpbin',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'},
        'json_response': True,
        'json_key': 'origin'
    },
    {
        'url': 'https://ipinfo.io/ip',
        'name': 'ipinfo',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://api.ipify.org',
        'name': 'ipify',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://ipv4.icanhazip.com',  # 使用IPv4专用URL
        'name': 'icanhazip-v4',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://v4.ident.me',  # 使用IPv4专用URL
        'name': 'ident.me-v4',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://checkip.amazonaws.com',
        'name': 'aws-checkip',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://ip4.seeip.org',
        'name': 'seeip-v4',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    }
]

# IPv6 IP获取服务列表（根据日志表现优化）
IPV6_SERVICES = [
    {
        'url': 'https://api6.ipify.org',
        'name': 'ipify-v6',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://ipv6.icanhazip.com',
        'name': 'icanhazip-v6',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://v6.ident.me',
        'name': 'ident.me-v6',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://ip6.seeip.org',
        'name': 'seeip-v6',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    },
    {
        'url': 'https://ipv6.whatismyipaddress.com/api',
        'name': 'whatismyip-v6',
        'timeout': 8,
        'headers': {'User-Agent': 'AliDDNS/1.0'}
    }
]

# Setup logging (修复重复日志问题)
def setup_logging():
    # 清除现有的handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 创建logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 文件handler
    file_handler = logging.FileHandler(CONFIG['log_file'])
    file_handler.setLevel(logging.INFO)
    
    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

class AliDDNS:
    def __init__(self):
        self.client = AcsClient(
            CONFIG['access_key_id'],
            CONFIG['access_secret'],
            'cn-hangzhou'
        )

    def get_current_ip(self, ip_type: str) -> str:
        """
        获取当前IP地址（IPv4或IPv6），使用优化的服务列表
        ip_type: 'A' for IPv4, 'AAAA' for IPv6
        """
        services = IPV4_SERVICES if ip_type == 'A' else IPV6_SERVICES
        ip_version = 'IPv4' if ip_type == 'A' else 'IPv6'
        
        # 不随机打乱，按配置的优先级顺序尝试
        last_exception = None
        
        for service in services:
            service_name = service['name']
            logging.info(f"尝试使用 {service_name} 获取 {ip_version} 地址")
            
            success = False
            for attempt in range(CONFIG['retry_attempts']):
                try:
                    request = Request(
                        service['url'], 
                        headers=service.get('headers', {})
                    )
                    
                    with urlopen(request, timeout=service.get('timeout', CONFIG['request_timeout'])) as response:
                        content = response.read().decode('utf-8').strip()
                        
                        # 处理JSON响应
                        if service.get('json_response', False):
                            data = json.loads(content)
                            ip_address = data.get(service['json_key'], '').strip()
                            # 处理可能的多个IP（如httpbin返回"ip1, ip2"的情况）
                            if ',' in ip_address:
                                ip_address = ip_address.split(',')[0].strip()
                        else:
                            ip_address = content
                        
                        # 验证IP地址格式
                        if self.validate_ip(ip_address, ip_type):
                            logging.info(f"成功从 {service_name} 获取到 {ip_version} 地址: {ip_address}")
                            return ip_address
                        else:
                            logging.warning(f"从 {service_name} 获取到无效的 {ip_version} 地址: {ip_address}")
                            break  # IP格式错误，跳过重试，尝试下一个服务
                            
                except (URLError, HTTPError, json.JSONDecodeError, UnicodeDecodeError) as e:
                    last_exception = e
                    if attempt < CONFIG['retry_attempts'] - 1:
                        wait_time = CONFIG['retry_delay'] * (attempt + 1)
                        logging.warning(f"{service_name} 第 {attempt+1} 次尝试失败: {str(e)}，{wait_time}秒后重试")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"{service_name} 所有尝试均失败: {str(e)}")
                        break  # 跳出重试循环，尝试下一个服务
                        
                except Exception as e:
                    last_exception = e
                    logging.error(f"{service_name} 发生未知错误: {str(e)}")
                    break  # 跳过当前服务，尝试下一个
        
        # 所有服务都失败
        error_msg = f"所有 {ip_version} 服务都无法获取IP地址"
        if last_exception:
            error_msg += f"，最后一个错误: {str(last_exception)}"
        
        logging.error(error_msg)
        raise Exception(error_msg)

    def validate_ip(self, ip_address: str, ip_type: str) -> bool:
        """验证IP地址格式"""
        if not ip_address:
            return False
            
        try:
            import ipaddress
            if ip_type == 'A':
                # 验证IPv4地址
                ipaddress.IPv4Address(ip_address)
                return True
            elif ip_type == 'AAAA':
                # 验证IPv6地址
                ipaddress.IPv6Address(ip_address)
                return True
        except ValueError:
            return False
        
        return False

    def get_domain_records(self, subdomain: str, record_type: str) -> dict:
        """从阿里云获取域名记录"""
        try:
            request = DescribeSubDomainRecordsRequest()
            request.set_accept_format('json')
            request.set_DomainName(CONFIG['domain'])
            request.set_SubDomain(subdomain)
            request.set_Type(record_type)
            response = self.client.do_action_with_exception(request)
            return json.loads(response)
        except (ClientException, ServerException) as e:
            logging.error(f"获取域名记录失败 {subdomain}: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"get_domain_records 发生未知错误: {str(e)}")
            raise

    def update_record(self, record_id: str, rr: str, record_type: str, value: str) -> None:
        """更新现有域名记录"""
        try:
            request = UpdateDomainRecordRequest()
            request.set_accept_format('json')
            request.set_RecordId(record_id)
            request.set_RR(rr)
            request.set_Type(record_type)
            request.set_Value(value)
            self.client.do_action_with_exception(request)
            logging.info(f"成功更新 {record_type} 记录 {rr} -> {value}")
        except (ClientException, ServerException) as e:
            logging.error(f"更新 {record_type} 记录失败 {rr}: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"update_record 发生未知错误: {str(e)}")
            raise

    def add_record(self, rr: str, record_type: str, value: str) -> None:
        """添加新的域名记录"""
        try:
            request = AddDomainRecordRequest()
            request.set_accept_format('json')
            request.set_DomainName(CONFIG['domain'])
            request.set_RR(rr)
            request.set_Type(record_type)
            request.set_Value(value)
            self.client.do_action_with_exception(request)
            logging.info(f"成功添加 {record_type} 记录 {rr} -> {value}")
        except (ClientException, ServerException) as e:
            logging.error(f"添加 {record_type} 记录失败 {rr}: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"add_record 发生未知错误: {str(e)}")
            raise

    def delete_records(self, rr: str, record_type: str) -> None:
        """删除现有域名记录"""
        try:
            request = DeleteSubDomainRecordsRequest()
            request.set_accept_format('json')
            request.set_DomainName(CONFIG['domain'])
            request.set_RR(rr)
            request.set_Type(record_type)
            self.client.do_action_with_exception(request)
            logging.info(f"成功删除 {record_type} 记录 {rr}")
        except (ClientException, ServerException) as e:
            logging.error(f"删除 {record_type} 记录失败 {rr}: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"delete_records 发生未知错误: {str(e)}")
            raise

    def process_dns(self, prefix: str, record_type: str) -> bool:
        """
        处理DNS更新
        返回 True 表示成功，False 表示失败
        """
        subdomain = f"{prefix}.{CONFIG['domain']}" if prefix != "@" else CONFIG['domain']
        ip_version = 'IPv4' if record_type == 'A' else 'IPv6'
        
        try:
            logging.info(f"开始处理 {ip_version} DNS更新，子域名: {subdomain}")
            
            # 获取当前IP地址
            current_ip = self.get_current_ip(record_type)
            logging.info(f"获取到 {ip_version} 地址: {current_ip}")
            
            # 获取现有域名记录
            domain_list = self.get_domain_records(subdomain, record_type)
            record_count = domain_list['TotalCount']
            logging.info(f"找到 {record_count} 条 {record_type} 记录")

            if record_count == 0:
                # 没有记录，添加新记录
                self.add_record(prefix, record_type, current_ip)
                logging.info(f"{ip_version} DNS记录添加完成")
            elif record_count == 1:
                # 有一条记录，检查是否需要更新
                current_record = domain_list['DomainRecords']['Record'][0]
                existing_ip = current_record['Value'].strip()
                
                if existing_ip != current_ip:
                    self.update_record(
                        current_record['RecordId'],
                        prefix,
                        record_type,
                        current_ip
                    )
                    logging.info(f"{ip_version} DNS记录更新完成: {existing_ip} -> {current_ip}")
                else:
                    logging.info(f"{ip_version} 地址未发生变化: {current_ip}")
            else:
                # 有多条记录，删除所有记录后重新添加
                logging.warning(f"发现多条 {record_type} 记录，清理后重新添加")
                self.delete_records(prefix, record_type)
                self.add_record(prefix, record_type, current_ip)
                logging.info(f"{ip_version} DNS记录清理并重新添加完成")
            
            return True
            
        except Exception as e:
            logging.error(f"处理 {ip_version} DNS时发生错误: {str(e)}")
            return False

def get_system_info():
    """获取系统信息用于日志"""
    try:
        import socket
        hostname = socket.gethostname()
        return f"主机: {hostname}"
    except:
        return "主机: 未知"

def main():
    """主函数"""
    load_config()
    setup_logging()
    logging.info("=" * 60)
    logging.info(f"阿里云DDNS更新程序启动 - {get_system_info()}")
    logging.info(f"域名: {CONFIG['domain']}")
    logging.info(f"IPv4前缀: {CONFIG['ipv4_prefix']}, IPv6前缀: {CONFIG['ipv6_prefix']}")
    logging.info("=" * 60)
    
    try:
        ddns = AliDDNS()
        success_count = 0
        total_count = 0
        
        # 处理IPv4
        if CONFIG['ipv4_enabled']:
            total_count += 1
            logging.info("开始处理IPv4更新")
            try:
                if ddns.process_dns(CONFIG['ipv4_prefix'], 'A'):
                    success_count += 1
                    logging.info("IPv4更新成功")
                else:
                    logging.warning("IPv4更新失败")
            except Exception as e:
                logging.error(f"IPv4处理过程发生异常: {str(e)}")
        
        # 处理IPv6
        if CONFIG['ipv6_enabled']:
            total_count += 1
            logging.info("开始处理IPv6更新")
            try:
                if ddns.process_dns(CONFIG['ipv6_prefix'], 'AAAA'):
                    success_count += 1
                    logging.info("IPv6更新成功")
                else:
                    logging.warning("IPv6更新失败")
            except Exception as e:
                logging.error(f"IPv6处理过程发生异常: {str(e)}")
        
        # 输出总结
        if success_count == total_count:
            logging.info(f"✓ DNS更新全部完成！成功: {success_count}/{total_count}")
        else:
            logging.warning(f"⚠ DNS更新部分完成。成功: {success_count}/{total_count}")
            
    except Exception as e:
        logging.error(f"程序执行过程中发生致命错误: {str(e)}")
    
    logging.info("阿里云DDNS更新程序结束")
    logging.info("=" * 60)

if __name__ == "__main__":
    main()