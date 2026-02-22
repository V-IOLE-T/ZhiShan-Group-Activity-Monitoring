"""
FileUploadService 单元测试

测试文件上传服务的各种场景
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.file_upload_service import FileUploadService


class TestFileUploadService:
    """FileUploadService 测试类"""

    def test_validate_file_type_with_allowed_image(self):
        """测试允许的图片类型验证"""
        assert FileUploadService._validate_file_type("image.jpg", {".jpg", ".png"}) is True
        assert FileUploadService._validate_file_type("image.jpeg", {".jpeg", ".png"}) is True
        assert FileUploadService._validate_file_type("image.PNG", {".jpg", ".png"}) is True

    def test_validate_file_type_with_disallowed_type(self):
        """测试不允许的文件类型"""
        assert FileUploadService._validate_file_type("file.exe", {".jpg", ".png"}) is False
        assert FileUploadService._validate_file_type("file.pdf", {".jpg", ".png"}) is False

    def test_validate_file_type_with_empty_name(self):
        """测试空文件名"""
        assert FileUploadService._validate_file_type("", {".jpg", ".png"}) is True

    @patch('services.file_upload_service.requests.patch')
    @patch('services.file_upload_service.requests.post')
    def test_upload_docx_image_success(self, mock_post, mock_patch):
        """测试 Docx 图片上传成功场景"""
        # Mock 创建 Block 响应
        create_response = Mock()
        create_response.json.return_value = {
            "code": 0,
            "data": {
                "children": [
                    {
                        "block_id": "test_block_id",
                        "image": {"token": "test_file_token"}
                    }
                ]
            }
        }

        # Mock 上传响应
        upload_response = Mock()
        upload_response.json.return_value = {"code": 0}

        # Mock batch_update 响应
        update_response = Mock()
        update_response.json.return_value = {"code": 0}

        mock_post.side_effect = [create_response, upload_response]
        mock_patch.return_value = update_response

        # 执行测试
        result = FileUploadService.upload_docx_image(
            image_data=b"fake_image_data",
            auth_token="Bearer test_token",
            doc_token="test_doc_token"
        )

        # 验证结果
        assert result is not None
        assert result["block_id"] == "test_block_id"
        assert result["file_token"] == "test_file_token"

    @patch('services.file_upload_service.requests.post')
    def test_upload_docx_image_create_block_failure(self, mock_post):
        """测试创建 Block 失败场景"""
        # Mock 创建 Block 失败响应
        create_response = Mock()
        create_response.json.return_value = {
            "code": -1,
            "msg": "Create block failed"
        }

        mock_post.return_value = create_response

        # 执行测试
        result = FileUploadService.upload_docx_image(
            image_data=b"fake_image_data",
            auth_token="Bearer test_token",
            doc_token="test_doc_token"
        )

        # 验证结果
        assert result is None

    @patch('services.file_upload_service.requests.post')
    def test_upload_to_bitable_success(self, mock_post):
        """测试 Bitable 文件上传成功场景"""
        # Mock 上传成功响应
        upload_response = Mock()
        upload_response.json.return_value = {
            "code": 0,
            "data": {
                "file_token": "test_file_token"
            }
        }

        mock_post.return_value = upload_response

        # 执行测试
        result = FileUploadService.upload_to_bitable(
            file_data=b"fake_file_data",
            app_token="test_app_token",
            table_id="test_table_id",
            auth_token="Bearer test_token",
            file_name="test.pdf"
        )

        # 验证结果
        assert result is not None
        assert result["file_token"] == "test_file_token"
        assert result["name"] == "test.pdf"
        assert result["size"] == len(b"fake_file_data")
        assert result["type"] == "file"

    def test_upload_to_bitable_no_app_token(self):
        """测试无 app_token 场景"""
        # 执行测试
        result = FileUploadService.upload_to_bitable(
            file_data=b"fake_file_data",
            app_token=None,
            table_id="test_table_id",
            auth_token="Bearer test_token",
            file_name="test.pdf"
        )

        # 验证结果
        assert result is None

    def test_upload_to_bitable_invalid_file_type(self):
        """测试无效文件类型"""
        # 执行测试
        result = FileUploadService.upload_to_bitable(
            file_data=b"fake_file_data",
            app_token="test_app_token",
            table_id="test_table_id",
            auth_token="Bearer test_token",
            file_name="test.exe"
        )

        # 验证结果
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
