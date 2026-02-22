"""
文件上传服务

统一处理飞书 Drive API 的文件上传逻辑，包括：
1. Docx 图片上传（三步流程：创建Block → 上传图片 → batch_update）
2. Bitable 文件上传（upload_all API）

此服务整合了以下重复代码：
- storage.py 中的 _upload_file_for_docx() 方法
- pin_monitor.py 中的 _upload_to_drive() 方法
- pin_daily_audit.py 中的 _upload_to_drive() 方法
"""

import requests
import time
import os
from typing import Optional, Dict, Set
from rate_limiter import with_rate_limit


class FileUploadService:
    """
    统一文件上传服务类

    提供静态方法处理飞书平台的文件上传，包括：
    - Docx 文档图片上传（三步流程）
    - Bitable 多维表格文件上传
    """

    # 支持的文件类型
    ALLOWED_IMAGE_TYPES: Set[str] = {".jpg", ".jpeg", ".png", ".gif"}
    ALLOWED_DOC_TYPES: Set[str] = {".pdf", ".docx", ".doc"}

    # API 超时配置（秒）
    TIMEOUT_CREATE_BLOCK = 10   # 创建 Block 超时
    TIMEOUT_UPLOAD = 30         # 上传文件超时
    TIMEOUT_BITABLE = 60        # Bitable 上传超时
    TIMEOUT_BATCH_UPDATE = 10   # Batch Update 超时

    # API 端点
    BASE_URL = "https://open.feishu.cn/open-apis"
    DOCX_CREATE_BLOCK_URL = f"{BASE_URL}/docx/v1/documents/{{doc_token}}/blocks/{{parent_id}}/children"
    DRIVE_UPLOAD_URL = f"{BASE_URL}/drive/v1/medias/upload_all"
    DOCX_BATCH_UPDATE_URL = f"{BASE_URL}/docx/v1/documents/{{doc_token}}/blocks/batch_update"

    @staticmethod
    @with_rate_limit
    def upload_docx_image(
        image_data: bytes,
        auth_token: str,
        doc_token: str,
        parent_id: str = None,
        file_name: str = None
    ) -> Optional[Dict[str, str]]:
        """
        上传图片到 Docx 文档（三步流程）

        三步上传流程：
        1. 创建空的图片 Block，获取 block_id 和 file_token
        2. 上传图片数据到该 file_token
        3. 通过 batch_update 将 Block 添加到文档

        Args:
            image_data: 图片二进制数据
            auth_token: 认证 Token（Bearer token 格式）
            doc_token: 文档 Token
            parent_id: 父块 ID（可选，默认使用 doc_token 作为父块）
            file_name: 文件名（可选，默认使用时间戳）

        Returns:
            成功返回 {"block_id": "xxx", "file_token": "yyy"}
            失败返回 None

        Example:
            >>> result = FileUploadService.upload_docx_image(
            ...     image_data=b"...",
            ...     auth_token="Bearer xxx",
            ...     doc_token="docx_token"
            ... )
            >>> if result:
            ...     print(f"Block ID: {result['block_id']}")
        """
        # 验证文件类型（如果提供了文件名）
        if file_name and not FileUploadService._validate_file_type(
            file_name, FileUploadService.ALLOWED_IMAGE_TYPES
        ):
            print(f"  > [FileUpload] ❌ 不支持的图片类型: {file_name}")
            return None

        # 默认父块 ID 为文档 Token
        if parent_id is None:
            parent_id = doc_token

        # 默认文件名
        if file_name is None:
            file_name = f"image_{int(time.time())}.png"

        # 构建请求头
        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}"
        }

        # 步骤1: 创建空的图片 Block
        print(f"  > [FileUpload] 步骤1: 创建空图片 Block...")
        create_url = FileUploadService.DOCX_CREATE_BLOCK_URL.format(doc_token=doc_token, parent_id=parent_id)
        empty_image_payload = {"children": [{"block_type": 27, "image": {} }]}

        try:
            response = requests.post(
                create_url, headers=headers, json=empty_image_payload, timeout=FileUploadService.TIMEOUT_CREATE_BLOCK
            )
            data = response.json()

            if data.get("code") != 0:
                print(f"  > [FileUpload] ❌ 创建图片 Block 失败: {data.get('msg', 'Unknown error')}")
                return None

            children = data.get("data", {}).get("children", [])
            if not children:
                print(f"  > [FileUpload] ❌ 创建图片 Block 无返回数据")
                return None

            image_block_id = children[0].get("block_id")
            file_token = children[0].get("image", {}).get("token")

            if not image_block_id or not file_token:
                print(f"  > [FileUpload] ❌ Block 响应缺少必要字段")
                return None

            print(f"  > [FileUpload] ✅ 创建空图片 Block: {image_block_id}")

        except requests.exceptions.Timeout:
            print(f"  > [FileUpload] ❌ 创建 Block 超时（>{FileUploadService.TIMEOUT_CREATE_BLOCK}秒）")
            return None
        except requests.exceptions.RequestException as e:
            print(f"  > [FileUpload] ❌ 创建 Block 请求异常: {e}")
            return None

        # 步骤2: 上传图片数据
        print(f"  > [FileUpload] 步骤2: 上传图片数据...")
        upload_success = FileUploadService._upload_image_data(
            image_data, file_token, headers
        )

        if not upload_success:
            print(f"  > [FileUpload] ❌ 图片数据上传失败")
            return None

        # 步骤3: Batch Update 更新图片 Block
        print(f"  > [FileUpload] 步骤3: 更新图片 Block...")
        batch_update_url = FileUploadService.DOCX_BATCH_UPDATE_URL.format(doc_token=doc_token)
        update_payload = {
            "requests": [
                {
                    "block_id": image_block_id,
                    "replace_image": {
                        "token": file_token
                    }
                }
            ]
        }

        try:
            # 注意：batch_update 使用 PATCH 方法，不是 POST
            update_response = requests.patch(
                batch_update_url, headers=headers, json=update_payload, timeout=FileUploadService.TIMEOUT_BATCH_UPDATE
            )
            update_data = update_response.json()

            if update_data.get("code") == 0:
                print(f"  > [FileUpload] ✅ 图片上传成功: {image_block_id}")
                return {
                    "block_id": image_block_id,
                    "file_token": file_token
                }
            else:
                print(f"  > [FileUpload] ❌ 更新图片 Block 失败: {update_data.get('msg', 'Unknown error')}")
                return None

        except requests.exceptions.Timeout:
            print(f"  > [FileUpload] ❌ Batch Update 超时（>{FileUploadService.TIMEOUT_BATCH_UPDATE}秒）")
            return None
        except requests.exceptions.RequestException as e:
            print(f"  > [FileUpload] ❌ Batch Update 请求异常: {e}")
            return None

    @staticmethod
    def _upload_image_data(image_data: bytes, file_token: str, headers: dict) -> bool:
        """
        上传图片数据到指定 file_token

        Args:
            image_data: 图片二进制数据
            file_token: 文件 Token
            headers: 请求头（包含 Authorization）

        Returns:
            成功返回 True，失败返回 False
        """
        upload_url = f"{FileUploadService.BASE_URL}/drive/v1/files/{file_token}/upload/{file_token}"

        files = {"file": ("image.png", image_data, "image/png")}

        # 使用重试机制上传
        for attempt in range(3):  # 最多重试2次（共3次尝试）
            try:
                response = requests.post(
                    upload_url, headers=headers, files=files, timeout=FileUploadService.TIMEOUT_UPLOAD
                )
                data = response.json()

                if data.get("code") == 0:
                    print(f"  > [FileUpload] ✅ 图片数据上传成功")
                    return True
                else:
                    if attempt < 2:  # 还有重试机会
                        wait_time = 2 ** attempt  # 指数退避：1秒 → 2秒
                        print(f"  > [FileUpload] ⚠️ 上传失败，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        print(f"  > [FileUpload] ❌ 图片数据上传失败: {data.get('msg', 'Unknown error')}")
                        return False

            except requests.exceptions.Timeout:
                if attempt < 2:
                    wait_time = 2 ** attempt
                    print(f"  > [FileUpload] ⚠️ 上传超时，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"  > [FileUpload] ❌ 上传超时（>{FileUploadService.TIMEOUT_UPLOAD}秒）")
                    return False
            except requests.exceptions.RequestException as e:
                if attempt < 2:
                    wait_time = 2 ** attempt
                    print(f"  > [FileUpload] ⚠️ 请求异常，{wait_time}秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"  > [FileUpload] ❌ 上传请求异常: {e}")
                    return False

        return False

    @staticmethod
    @with_rate_limit
    def upload_to_bitable(
        file_data: bytes,
        app_token: str,
        table_id: str,
        auth_token: str,
        file_name: str
    ) -> Optional[Dict[str, any]]:
        """
        上传文件到多维表格

        Args:
            file_data: 文件二进制数据
            app_token: 应用 Token
            table_id: 表 ID（预留参数，当前未使用）
            auth_token: 认证 Token（Bearer token 格式）
            file_name: 文件名

        Returns:
            成功返回 {
                "file_token": "xxx",
                "name": "文件名",
                "size": 文件大小,
                "type": "file"
            }
            失败返回 None

        Example:
            >>> result = FileUploadService.upload_to_bitable(
            ...     file_data=b"...",
            ...     app_token="app_xxx",
            ...     table_id="table_xxx",
            ...     auth_token="Bearer xxx",
            ...     file_name="document.pdf"
            ... )
            >>> if result:
            ...     print(f"File Token: {result['file_token']}")
        """
        if not app_token:
            print(f"  > [FileUpload] ❌ app_token 未提供")
            return None

        # 验证文件类型
        if not FileUploadService._validate_file_type(
            file_name, FileUploadService.ALLOWED_IMAGE_TYPES | FileUploadService.ALLOWED_DOC_TYPES
        ):
            print(f"  > [FileUpload] ❌ 不支持的文件类型: {file_name}")
            return None

        # 构建请求头
        headers = {
            "Authorization": auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}"
        }

        # 构建表单数据
        form_data = {
            "file_name": file_name,
            "parent_type": "bitable_file",
            "parent_node": app_token,
            "size": str(len(file_data)),
        }

        files = {"file": (file_name, file_data)}

        # 使用重试机制上传
        for attempt in range(3):  # 最多重试2次
            try:
                print(f"  > [FileUpload] 上传文件到 Bitable: {file_name}")
                response = requests.post(
                    FileUploadService.DRIVE_UPLOAD_URL,
                    headers=headers,
                    data=form_data,
                    files=files,
                    timeout=FileUploadService.TIMEOUT_BITABLE
                )
                result = response.json()

                if result.get("code") == 0:
                    file_token = result.get("data", {}).get("file_token")
                    if not file_token:
                        print(f"  > [FileUpload] ❌ 响应缺少 file_token")
                        return None

                    print(f"  > [FileUpload] ✅ 文件已上传到 Bitable: {file_token}")
                    return {
                        "file_token": file_token,
                        "name": file_name,
                        "size": len(file_data),
                        "type": "file",
                    }
                else:
                    if attempt < 2:
                        wait_time = 2 ** attempt
                        print(f"  > [FileUpload] ⚠️ 上传失败，{wait_time}秒后重试: {result.get('msg', 'Unknown error')}")
                        time.sleep(wait_time)
                    else:
                        print(f"  > [FileUpload] ❌ 文件上传失败: {result.get('msg', 'Unknown error')}")
                        return None

            except requests.exceptions.Timeout:
                if attempt < 2:
                    wait_time = 2 ** attempt
                    print(f"  > [FileUpload] ⚠️ 上传超时，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"  > [FileUpload] ❌ 上传超时（>{FileUploadService.TIMEOUT_BITABLE}秒）")
                    return None
            except requests.exceptions.RequestException as e:
                if attempt < 2:
                    wait_time = 2 ** attempt
                    print(f"  > [FileUpload] ⚠️ 请求异常，{wait_time}秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"  > [FileUpload] ❌ 上传请求异常: {e}")
                    return None

        return None

    @staticmethod
    def _validate_file_type(file_name: str, allowed_types: Set[str]) -> bool:
        """
        验证文件类型

        Args:
            file_name: 文件名
            allowed_types: 允许的文件扩展名集合（如 {".jpg", ".png"}）

        Returns:
            文件类型在允许列表中返回 True，否则返回 False

        Example:
            >>> FileUploadService._validate_file_type("image.jpg", {".jpg", ".png"})
            True
            >>> FileUploadService._validate_file_type("file.exe", {".jpg", ".png"})
            False
        """
        if not file_name:
            return True  # 无文件名时不验证

        # 获取文件扩展名（转为小写）
        _, ext = os.path.splitext(file_name.lower())
        return ext in allowed_types
