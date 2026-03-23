#!/usr/bin/env python3
"""
JWT Secret Key 生成与验证工具
支持密钥强度检测、多种格式输出、批量生成
"""

import argparse
import secrets
import base64
import sys
import math
from typing import Tuple, Optional


class KeyStrengthValidator:
    """密钥强度验证器"""

    # 熵值阈值（位数）
    ENTROPY_THRESHOLDS = {
        'weak': 128,  # 低于此值视为弱密钥
        'moderate': 192,  # 中等强度
        'strong': 256  # 强密钥
    }

    @staticmethod
    def calculate_entropy(key: str, format_type: str = 'base64') -> float:
        """
        计算密钥的熵值

        Args:
            key: 密钥字符串
            format_type: 密钥格式 ('base64', 'urlsafe', 'hex')

        Returns:
            熵值（位数）
        """
        if format_type in ['base64', 'urlsafe']:
            # Base64 字符集大小：64
            charset_size = 64
            # 移除 padding 的影响
            effective_length = len(key)
        elif format_type == 'hex':
            # 十六进制字符集大小：16
            charset_size = 16
            effective_length = len(key)
        else:
            # 默认假设 ASCII 字符集
            charset_size = 95  # 可打印 ASCII 字符数
            effective_length = len(key)

        # 最大可能熵值 = 长度 * log2(字符集大小)
        max_entropy = effective_length * math.log2(charset_size)

        # 如果是随机生成的，实际熵值接近最大熵值
        # 这里返回最大可能熵值作为估算
        return max_entropy

    @staticmethod
    def validate_key_strength(key: str, format_type: str = 'base64') -> Tuple[bool, str, dict]:
        """
        验证密钥强度

        Args:
            key: 要验证的密钥
            format_type: 密钥格式

        Returns:
            (是否通过, 消息, 详细信息)
        """
        details = {}

        # 1. 检查长度
        length = len(key)
        details['length'] = length
        if format_type in ['base64', 'urlsafe']:
            min_length = 32  # 32字节的Base64编码后约43字符
            if length < 32:
                return False, f"密钥长度不足: {length} 字符 (建议至少32字符)", details
        elif format_type == 'hex':
            min_length = 64  # 32字节的十六进制是64字符
            if length < 64:
                return False, f"密钥长度不足: {length} 字符 (建议至少64字符)", details

        # 2. 计算熵值
        entropy = KeyStrengthValidator.calculate_entropy(key, format_type)
        details['entropy'] = round(entropy, 2)

        # 3. 检查字符多样性
        unique_chars = len(set(key))
        details['unique_chars'] = unique_chars
        details['charset_size'] = unique_chars

        if unique_chars < 10:
            return False, f"字符多样性不足: 仅使用 {unique_chars} 种不同字符", details

        # 4. 检查是否包含常见模式
        patterns = []
        if key.isalpha():
            patterns.append("仅包含字母")
        if key.isdigit():
            patterns.append("仅包含数字")
        if key.islower():
            patterns.append("仅包含小写字母")
        if key.isupper():
            patterns.append("仅包含大写字母")

        details['patterns'] = patterns

        # 5. 根据熵值评估强度
        if entropy >= KeyStrengthValidator.ENTROPY_THRESHOLDS['strong']:
            strength = "强"
            passed = True
            message = f"密钥强度: {strength} (熵值: {entropy:.1f}位)"
        elif entropy >= KeyStrengthValidator.ENTROPY_THRESHOLDS['moderate']:
            strength = "中等"
            passed = True
            message = f"密钥强度: {strength} (熵值: {entropy:.1f}位)"
        elif entropy >= KeyStrengthValidator.ENTROPY_THRESHOLDS['weak']:
            strength = "弱"
            passed = False
            message = f"密钥强度: {strength} (熵值: {entropy:.1f}位) - 建议使用更强的密钥"
        else:
            strength = "极弱"
            passed = False
            message = f"密钥强度: {strength} (熵值: {entropy:.1f}位) - 不安全，必须更换"

        details['strength'] = strength

        if patterns:
            message += f" | 警告: {', '.join(patterns)}"

        return passed, message, details


class JWTKeyGenerator:
    """JWT Secret Key 生成器"""

    def __init__(self, validate_strength: bool = True):
        self.validate_strength = validate_strength
        self.validator = KeyStrengthValidator()

    def generate_key(self, length: int = 32, format_type: str = 'base64',
                     validate: bool = True) -> Tuple[str, dict]:
        """
        生成 JWT secret key

        Args:
            length: 密钥长度（字节数）
            format_type: 输出格式 ('base64', 'urlsafe', 'hex')
            validate: 是否验证密钥强度

        Returns:
            (密钥, 验证信息)
        """
        # 生成随机字节
        random_bytes = secrets.token_bytes(length)

        # 根据格式转换
        if format_type == 'base64':
            key = base64.b64encode(random_bytes).decode('utf-8')
        elif format_type == 'urlsafe':
            key = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
        elif format_type == 'hex':
            key = random_bytes.hex()
        else:
            raise ValueError(f"不支持的格式: {format_type}")

        validation_info = {}

        # 验证密钥强度
        if validate:
            passed, message, details = self.validator.validate_key_strength(key, format_type)
            validation_info = {
                'passed': passed,
                'message': message,
                'details': details
            }

            if not passed:
                # 如果不通过，可以选择重新生成或返回警告
                validation_info['warning'] = message

        return key, validation_info

    def generate_multiple(self, count: int = 1, length: int = 32,
                          format_type: str = 'base64') -> list:
        """生成多个密钥"""
        keys = []
        for i in range(count):
            key, validation = self.generate_key(length, format_type, validate=True)
            keys.append({
                'index': i + 1,
                'key': key,
                'validation': validation
            })
        return keys


def format_validation_output(validation: dict) -> str:
    """格式化验证信息输出"""
    if not validation:
        return ""

    output = []

    if 'passed' in validation:
        status = "✓ 通过" if validation['passed'] else "✗ 不通过"
        output.append(f"  验证状态: {status}")

    if 'message' in validation:
        output.append(f"  信息: {validation['message']}")

    if 'details' in validation:
        details = validation['details']
        output.append(f"  详细信息:")
        output.append(f"    - 长度: {details.get('length', 'N/A')} 字符")
        output.append(f"    - 熵值: {details.get('entropy', 'N/A')} 位")
        output.append(f"    - 强度等级: {details.get('strength', 'N/A')}")
        output.append(f"    - 唯一字符数: {details.get('unique_chars', 'N/A')}")

        if details.get('patterns'):
            output.append(f"    - 警告模式: {', '.join(details['patterns'])}")

    if 'warning' in validation:
        output.append(f"  ⚠ 警告: {validation['warning']}")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description='JWT Secret Key 生成与验证工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                          # 生成默认密钥并验证
  %(prog)s -l 64 -f hex             # 生成64字节十六进制密钥
  %(prog)s -c 5                     # 生成5个密钥
  %(prog)s --no-validate            # 生成密钥但不验证
  %(prog)s -v "your-secret-key"     # 验证现有密钥强度
        """
    )

    parser.add_argument('-l', '--length', type=int, default=32,
                        help='密钥长度（字节），默认32')
    parser.add_argument('-f', '--format', choices=['base64', 'urlsafe', 'hex'],
                        default='base64', help='输出格式，默认base64')
    parser.add_argument('-c', '--count', type=int, default=1,
                        help='生成密钥数量，默认1')
    parser.add_argument('--no-validate', action='store_true',
                        help='跳过密钥强度验证')
    parser.add_argument('-v', '--validate-key', type=str, metavar='KEY',
                        help='验证指定密钥的强度')

    args = parser.parse_args()

    # 创建生成器
    generator = JWTKeyGenerator(validate_strength=not args.no_validate)

    # 验证模式
    if args.validate_key:
        print("=== JWT Secret Key 强度验证 ===")
        print(f"待验证密钥: {args.validate_key}")
        print("-" * 50)

        # 自动检测格式
        detected_format = 'base64'
        if all(c in '0123456789abcdef' for c in args.validate_key.lower()):
            detected_format = 'hex'
        elif '-' in args.validate_key or '_' in args.validate_key:
            detected_format = 'urlsafe'

        passed, message, details = KeyStrengthValidator.validate_key_strength(
            args.validate_key, detected_format
        )

        print(f"检测格式: {detected_format}")
        print(f"验证结果: {'✓ 通过' if passed else '✗ 不通过'}")
        print(f"强度评估: {details.get('strength', 'N/A')}")
        print(f"熵值: {details.get('entropy', 'N/A'):.1f} 位")
        print(f"密钥长度: {details.get('length', 'N/A')} 字符")
        print(f"字符集大小: {details.get('charset_size', 'N/A')}")

        if details.get('patterns'):
            print(f"⚠ 警告: {', '.join(details['patterns'])}")

        print(f"\n建议: {'密钥强度良好' if passed else '请使用更强的密钥'}")
        return

    # 生成模式
    print(f"=== JWT Secret Key 生成工具 ===")
    print(f"配置: {args.length}字节, {args.format}格式, 生成{args.count}个")
    if args.no_validate:
        print("⚠ 注意: 已跳过密钥强度验证")
    print("=" * 50)

    # 生成密钥
    keys = generator.generate_multiple(args.count, args.length, args.format)

    for key_info in keys:
        print(f"\n密钥 #{key_info['index']}:")
        print(f"  {key_info['key']}")

        if not args.no_validate and key_info['validation']:
            print(format_validation_output(key_info['validation']))

    # 输出环境变量配置示例
    if keys:
        print("\n" + "=" * 50)
        print("环境变量配置示例:")
        print(f'JWT_SECRET_KEY="{keys[0]["key"]}"')
        print(f'JWT_ALGORITHM="HS256"')
        print(f'JWT_EXPIRES_IN="7d"')

        # 输出安全建议
        print("\n安全建议:")
        print("  1. 将密钥存储在环境变量或密钥管理服务中")
        print("  2. 不要将密钥提交到版本控制系统")
        print("  3. 定期轮换密钥（建议每90天）")
        print("  4. 不同环境使用不同的密钥")
        print("  5. 确保密钥强度至少达到256位熵值")

        # 如果有弱密钥，给出额外警告
        weak_keys = [k for k in keys if k['validation'] and not k['validation'].get('passed', True)]
        if weak_keys:
            print("\n⚠ 警告: 检测到弱密钥，建议增加密钥长度或使用更强的生成算法")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)