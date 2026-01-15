# 文件上传逻辑重构指南

## 背景

在P3改进过程中，发现`pin_monitor.py`和`storage.py`中存在重复的文件上传代码（约50行）。为提升代码可维护性，已将公共逻辑提取到`utils.py`中。

## 新增公共函数

### `upload_file_to_bitable()`

位置: `utils.py:220-321`

```python
from utils import upload_file_to_bitable

result = upload_file_to_bitable(
    file_content=file_bytes,
    file_name="example.txt",
    app_token=os.getenv('BITABLE_APP_TOKEN'),
    auth_token=auth.get_tenant_access_token()
)

if result:
    file_token = result['file_token']
    print(f"上传成功: {file_token}")
```

**参数:**
- `file_content` (bytes): 文件内容
- `file_name` (str): 文件名
- `app_token` (str): 多维表格app_token
- `auth_token` (str): 认证token
- `upload_url` (str, 可选): 上传接口地址

**返回值:**
- 成功: `{"file_token": "xxx", "name": "...", "size": 1024, "type": "file"}`
- 失败: `None`

## 重构建议

### 1. pin_monitor.py

**当前代码** (line 427-463):
```python
def _upload_pin_attachment_bitable(self, file_content, file_name):
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"

    app_token = os.getenv('BITABLE_APP_TOKEN')
    form_data = {
        'file_name': file_name,
        'parent_type': 'bitable_file',
        'parent_node': app_token,
        'size': str(len(file_content))
    }

    files = {'file': (file_name, file_content)}
    upload_headers = {
        "Authorization": f"Bearer {self.auth.get_tenant_access_token()}"
    }

    try:
        response = requests.post(url, headers=upload_headers, data=form_data, files=files, timeout=60)
        result = response.json()

        if result.get('code') == 0:
            file_token = result.get('data', {}).get('file_token')
            if file_token:
                print(f"  > [Pin附件] ✅ 附件已上传: {file_token}")
                return {
                    "file_token": file_token,
                    "name": file_name,
                    "size": len(file_content),
                    "type": "file"
                }
        else:
            print(f"  > [Pin附件] ❌ 上传失败: {result}")
            return None
    except Exception as e:
        print(f"  > [Pin附件] ❌ 上传异常: {e}")
        return None
```

**重构后**:
```python
from utils import upload_file_to_bitable

def _upload_pin_attachment_bitable(self, file_content, file_name):
    """上传Pin消息的附件到Bitable"""
    import os

    app_token = os.getenv('BITABLE_APP_TOKEN')
    auth_token = self.auth.get_tenant_access_token()

    result = upload_file_to_bitable(
        file_content=file_content,
        file_name=file_name,
        app_token=app_token,
        auth_token=auth_token
    )

    if result:
        print(f"  > [Pin附件] ✅ 附件已上传: {result['file_token']}")
    else:
        print(f"  > [Pin附件] ❌ 附件上传失败")

    return result
```

**代码减少**: 36行 → 15行 (**-58%**)

### 2. storage.py

**当前代码** (line 438-495):
```python
def _upload_attachment_bitable(self, file_content, file_name):
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"

    form_data = {
        'file_name': file_name,
        'parent_type': 'bitable_file',
        'parent_node': self.app_token,
        'size': str(len(file_content))
    }

    files = {
        'file': (file_name, file_content)
    }

    upload_headers = {
        "Authorization": self.auth.get_headers()["Authorization"]
    }

    try:
        response = requests.post(url, headers=upload_headers, data=form_data, files=files, timeout=60)

        if response.status_code != 200:
            print(f"  > [附件] ❌ 上传素材 HTTP 错误: {response.status_code}")
            print(f"  > [附件] 响应内容: {response.text[:200]}")
            return None

        try:
            result = response.json()
        except Exception as e:
            print(f"  > [附件] ❌ 解析响应 JSON 失败: {e}")
            print(f"  > [附件] 原始响应: {response.text[:200]}")
            return None

        if result.get('code') == 0:
            data_obj = result.get('data', {})
            file_token = data_obj.get('file_token')
            if file_token:
                print(f"  > [附件] ✅ 素材已上传到多维表格: {file_token}")
                return {
                    "file_token": file_token,
                    "name": file_name,
                    "size": len(file_content),
                    "type": "file"
                }
            else:
                print(f"  > [附件] ❌ 响应中未找到 file_token: {result}")
                return None
        else:
            print(f"  > [附件] ❌ 上传素材失败: {result}")
            return None
    except Exception as e:
        print(f"  > [附件] ❌ 上传素材出错: {e}")
        return None
```

**重构后**:
```python
from utils import upload_file_to_bitable

def _upload_attachment_bitable(self, file_content, file_name):
    """上传附件到Bitable"""
    auth_token = self.auth.get_tenant_access_token()

    result = upload_file_to_bitable(
        file_content=file_content,
        file_name=file_name,
        app_token=self.app_token,
        auth_token=auth_token
    )

    if result:
        print(f"  > [附件] ✅ 素材已上传到多维表格: {result['file_token']}")
    else:
        print(f"  > [附件] ❌ 附件上传失败")

    return result
```

**代码减少**: 57行 → 13行 (**-77%**)

## 重构收益

### 代码质量提升

| 指标 | 重构前 | 重构后 | 改善 |
|-----|-------|-------|-----|
| 代码重复 | 2处（共93行） | 0处 | **-100%** |
| 文件上传函数总行数 | 93行 | 28行 + 102行工具函数 | -63行净减少 |
| 维护点 | 2个独立实现 | 1个统一实现 | **集中维护** |
| 错误处理一致性 | 不一致 | 完全一致 | **✅** |
| 可测试性 | 难以单独测试 | 易于单元测试 | **✅** |

### 具体优势

1. **消除重复代码**
   - 2处几乎相同的上传逻辑合并为1个公共函数
   - 减少维护负担

2. **一致的错误处理**
   - 统一的HTTP错误检查
   - 统一的JSON解析错误处理
   - 统一的超时处理

3. **更好的日志输出**
   - 统一的日志格式
   - 清晰的错误信息

4. **易于单元测试**
   - 可以独立测试文件上传逻辑
   - Mock requests更简单

5. **易于扩展**
   - 需要修改上传逻辑时只改一处
   - 新增上传场景直接调用

## 单元测试

建议添加的测试 (tests/test_utils.py):

```python
class TestUploadFileToBitable(unittest.TestCase):
    """测试文件上传功能"""

    @patch('utils.requests.post')
    def test_upload_success(self, mock_post):
        """测试上传成功"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'code': 0,
            'data': {'file_token': 'test_token_123'}
        }
        mock_post.return_value = mock_response

        result = upload_file_to_bitable(
            file_content=b"test content",
            file_name="test.txt",
            app_token="bascn123",
            auth_token="token_abc"
        )

        self.assertIsNotNone(result)
        self.assertEqual(result['file_token'], 'test_token_123')
        self.assertEqual(result['name'], 'test.txt')

    @patch('utils.requests.post')
    def test_upload_http_error(self, mock_post):
        """测试HTTP错误"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = upload_file_to_bitable(
            file_content=b"test",
            file_name="test.txt",
            app_token="bascn123",
            auth_token="token_abc"
        )

        self.assertIsNone(result)
```

## 实施步骤

### 第一阶段：准备工作 ✅
- [x] 在utils.py中添加upload_file_to_bitable函数
- [x] 添加完整的文档字符串和类型提示
- [x] 创建本重构指南文档

### 第二阶段：测试（可选）
- [ ] 为upload_file_to_bitable添加单元测试
- [ ] 确保测试覆盖成功、失败、超时等场景

### 第三阶段：重构代码（可选）
- [ ] 修改pin_monitor.py使用新函数
- [ ] 修改storage.py使用新函数
- [ ] 运行现有测试确保功能不变

### 第四阶段：验证（可选）
- [ ] 运行完整测试套件
- [ ] 手动测试文件上传功能
- [ ] 检查日志输出是否正常

## 注意事项

### 向后兼容性
- 新函数返回格式与旧代码完全一致
- 调用方代码无需修改逻辑，只需替换上传函数调用

### 日志输出
重构后的日志输出会有轻微变化：
- **旧**: `[Pin附件] ✅ 附件已上传: token123`
- **新**: `[文件上传] ✅ 文件已上传: test.txt -> token123`

如需保持原有日志格式，可在调用方添加额外的日志输出。

### 性能影响
- 无性能影响
- 函数调用开销可忽略不计

## 其他潜在重构

### 1. 下载文件
如果项目中有多处下载文件的代码，可以类似地提取为`download_file_from_bitable()`

### 2. API调用
可以考虑创建更通用的`call_feishu_api()`函数，统一处理：
- 认证token获取
- 速率限制
- 错误处理
- 重试逻辑

## 总结

提取文件上传公共逻辑是一个典型的DRY（Don't Repeat Yourself）原则应用：

**改进前**:
- ❌ 93行重复代码
- ❌ 2个独立维护点
- ❌ 不一致的错误处理
- ❌ 难以单独测试

**改进后**:
- ✅ 102行统一实现
- ✅ 1个集中维护点
- ✅ 一致的错误处理
- ✅ 易于单元测试
- ✅ 调用方代码更简洁

这个重构提升了代码质量，降低了维护成本，并为未来扩展奠定了基础。

---

**创建日期**: 2026-01-15
**相关文件**: utils.py, pin_monitor.py, storage.py
**状态**: ✅ 公共函数已创建，待实施重构
