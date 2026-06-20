"""生成和风天气 JWT 认证所需的 Ed25519 密钥对。

公钥需要手动上传到和风天气控制台换取 KID；私钥仅保留在本地 secrets/ 目录，
绝不提交、绝不上传。
"""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "secrets" / "qweather"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = OUTPUT_DIR / "ed25519-private.pem"
    public_path = OUTPUT_DIR / "ed25519-public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    print(f"私钥已生成（仅本地保留，不要上传/提交）：{private_path}")
    print(f"公钥已生成（上传到和风天气控制台换取 KID）：{public_path}")
    print()
    print("公钥内容：")
    print(public_pem.decode())


if __name__ == "__main__":
    main()
