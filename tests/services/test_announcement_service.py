from services.announcement_service import AnnouncementService


def test_parse_tags_default():
    tags = AnnouncementService.parse_tags(None)
    assert tags == ["公告", "通知"]


def test_parse_tags_custom():
    tags = AnnouncementService.parse_tags("公告, 通知, 系统播报")
    assert tags == ["公告", "通知", "系统播报"]


def test_is_announcement_text_supports_half_and_full_width_hash():
    assert AnnouncementService.is_announcement_text("#公告 今日更新")
    assert AnnouncementService.is_announcement_text("＃通知 今晚维护")


def test_is_announcement_message_from_feishu_text_content():
    content = '{"text":"#公告 今日晚8点发布新规则"}'
    assert AnnouncementService.is_announcement_message(content)
    assert not AnnouncementService.is_announcement_message('{"text":"普通讨论消息"}')
