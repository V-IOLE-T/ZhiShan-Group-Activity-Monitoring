import json

from message_renderer import MessageToDocxConverter


class DummyStorage:
    def transfer_image_to_docx(self, message_id, image_key, doc_id):
        return f"img_token_{image_key}"


def _collect_text_runs(blocks):
    runs = []
    for block in blocks:
        if block.get("block_type") == 2:
            runs.extend(block.get("text", {}).get("elements", []))
        elif block.get("block_type") in (3, 4, 5, 6, 7, 8, 9, 10, 11):
            heading_key = next((k for k in block.keys() if k.startswith("heading")), None)
            if heading_key:
                runs.extend(block.get(heading_key, {}).get("elements", []))
    return runs


def test_convert_handles_nested_post_structure_as_rich_text():
    converter = MessageToDocxConverter(DummyStorage())
    content = {
        "post": {
            "zh_cn": {
                "title": "公告标题",
                "content": [[
                    {"tag": "text", "text": "重点", "style": ["bold"]},
                    {"tag": "a", "text": "链接", "href": "https://example.com"},
                ]]
            }
        }
    }

    blocks = converter.convert(
        json.dumps(content, ensure_ascii=False),
        message_id="om_test_1",
        doc_id="doc_test_1",
        sender_name="Alice",
        send_time="2026-02-24 09:00:00",
    )

    runs = _collect_text_runs(blocks)
    assert any(r.get("text_run", {}).get("content") == "重点" for r in runs)
    assert any(
        r.get("text_run", {}).get("content") == "重点"
        and r.get("text_run", {}).get("text_element_style", {}).get("bold") is True
        for r in runs
    )
    assert any(
        r.get("text_run", {}).get("content") == "链接"
        and r.get("text_run", {}).get("text_element_style", {}).get("link", {}).get("url") == "https://example.com"
        for r in runs
    )


def test_convert_reply_message_keeps_rich_text_elements():
    converter = MessageToDocxConverter(DummyStorage())
    content = {
        "post": {
            "zh_cn": {
                "title": "回复标题",
                "content": [[
                    {"tag": "text", "text": "回复正文", "style": ["italic"]},
                    {"tag": "at", "user_name": "Bob"},
                ]]
            }
        }
    }

    blocks = converter.convert(
        json.dumps(content, ensure_ascii=False),
        message_id="om_test_2",
        doc_id="doc_test_2",
        sender_name="Carol",
        send_time="2026-02-24 10:00:00",
        is_reply=True,
        parent_sender_name="Bob",
    )

    # 回复消息不追加分割线
    assert not any(block.get("block_type") == 22 for block in blocks)

    runs = _collect_text_runs(blocks)
    assert any(r.get("text_run", {}).get("content") == "回复正文" for r in runs)
    assert any(
        r.get("text_run", {}).get("content") == "回复正文"
        and r.get("text_run", {}).get("text_element_style", {}).get("italic") is True
        for r in runs
    )
    assert any("@Bob" in r.get("text_run", {}).get("content", "") for r in runs)
