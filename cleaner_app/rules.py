from __future__ import annotations

from .models import CleanupRule, ItemKind, RiskLevel


SYSTEM_RULES: tuple[CleanupRule, ...] = (
    CleanupRule(
        rule_id="system.user_temp",
        title="当前用户临时文件",
        vendor="Windows",
        category="安全垃圾",
        description="应用运行时留下的临时文件，通常可重新生成。",
        safe_reason="只扫描用户临时目录，不触碰文档、桌面和系统目录。",
        risk=RiskLevel.LOW,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=("%TEMP%\\*", "%TMP%\\*"),
        default_selected=True,
        requires_confirmation=False,
    ),
    CleanupRule(
        rule_id="system.windows_temp",
        title="Windows 临时目录",
        vendor="Windows",
        category="安全垃圾",
        description="系统和安装程序留下的临时文件。",
        safe_reason="仅清理 C:\\Windows\\Temp 下的普通文件，受保护路径会被再次拦截。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=("%WINDIR%\\Temp\\*",),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="system.crash_dumps",
        title="崩溃转储和错误报告",
        vendor="Windows",
        category="安全垃圾",
        description="程序崩溃后生成的诊断文件，占用空间较大。",
        safe_reason="删除后只影响历史诊断，不影响程序数据。",
        risk=RiskLevel.LOW,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%LOCALAPPDATA%\\CrashDumps\\*",
            "%LOCALAPPDATA%\\Microsoft\\Windows\\WER\\ReportArchive\\*",
            "%LOCALAPPDATA%\\Microsoft\\Windows\\WER\\ReportQueue\\*",
        ),
        default_selected=True,
        requires_confirmation=False,
    ),
)


BROWSER_RULES: tuple[CleanupRule, ...] = (
    CleanupRule(
        rule_id="browser.chrome_cache",
        title="Chrome 缓存",
        vendor="Google Chrome",
        category="浏览器隐私",
        description="网页缓存、GPU 缓存和临时资源。",
        safe_reason="不删除书签、密码、历史记录数据库或用户配置。",
        risk=RiskLevel.LOW,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%LOCALAPPDATA%\\Google\\Chrome\\User Data\\*\\Cache\\*",
            "%LOCALAPPDATA%\\Google\\Chrome\\User Data\\*\\Code Cache\\*",
            "%LOCALAPPDATA%\\Google\\Chrome\\User Data\\*\\GPUCache\\*",
        ),
        default_selected=True,
        requires_confirmation=False,
    ),
    CleanupRule(
        rule_id="browser.edge_cache",
        title="Edge 缓存",
        vendor="Microsoft Edge",
        category="浏览器隐私",
        description="网页缓存、GPU 缓存和临时资源。",
        safe_reason="不删除收藏夹、密码、历史记录数据库或用户配置。",
        risk=RiskLevel.LOW,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\*\\Cache\\*",
            "%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\*\\Code Cache\\*",
            "%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\*\\GPUCache\\*",
        ),
        default_selected=True,
        requires_confirmation=False,
    ),
    CleanupRule(
        rule_id="browser.firefox_cache",
        title="Firefox 缓存",
        vendor="Mozilla Firefox",
        category="浏览器隐私",
        description="Firefox 页面缓存和缩略图缓存。",
        safe_reason="只清理缓存目录，不删除配置、书签或登录信息。",
        risk=RiskLevel.LOW,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=("%LOCALAPPDATA%\\Mozilla\\Firefox\\Profiles\\*\\cache2\\*",),
        default_selected=True,
        requires_confirmation=False,
    ),
)


STUBBORN_SOFTWARE_RULES: tuple[CleanupRule, ...] = (
    CleanupRule(
        rule_id="pup.360_cache",
        title="360 系列缓存与日志",
        vendor="360",
        category="已卸载软件残留",
        description="360 安全卫士、360 浏览器等软件卸载后留下的缓存、日志和临时文件。",
        safe_reason="只命中缓存、日志、temp、download 等残留位置，不删除主程序目录。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\360*\\*Cache*\\*",
            "%LOCALAPPDATA%\\360*\\*Cache*\\*",
            "%LOCALAPPDATA%\\360*\\*Temp*\\*",
            "%PROGRAMDATA%\\360*\\*log*\\*",
            "%PROGRAMDATA%\\360*\\*temp*\\*",
        ),
        process_names=("360tray.exe", "360safe.exe", "360sd.exe", "360se.exe"),
        service_keywords=("360", "qihu", "qhactivedefense"),
        task_keywords=("360", "qihu"),
        registry_keywords=("360", "qihu", "360safe"),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="pup.tencent_manager_cache",
        title="腾讯电脑管家缓存与日志",
        vendor="Tencent",
        category="已卸载软件残留",
        description="腾讯电脑管家、QQ 浏览器等软件卸载后留下的缓存、日志和临时文件。",
        safe_reason="只清理缓存和日志，不删除 QQ/微信聊天记录。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\Tencent\\QQBrowser\\*Cache*\\*",
            "%LOCALAPPDATA%\\Tencent\\QQBrowser\\*Cache*\\*",
            "%PROGRAMDATA%\\Tencent\\QQPCMgr\\*log*\\*",
            "%PROGRAMDATA%\\Tencent\\QQPCMgr\\*temp*\\*",
            "%LOCALAPPDATA%\\Tencent\\QQPCMgr\\*Cache*\\*",
        ),
        process_names=("QQPCTray.exe", "QQPCRTP.exe", "QQBrowser.exe"),
        service_keywords=("qqpc", "tencent"),
        task_keywords=("qqpc", "tencent", "qqbrowser"),
        registry_keywords=("qqpcmgr", "qqbrowser", "tencent"),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="pup.kingsoft_cache",
        title="金山/猎豹系列缓存与日志",
        vendor="Kingsoft",
        category="已卸载软件残留",
        description="金山毒霸、猎豹浏览器等软件卸载后留下的缓存和日志。",
        safe_reason="只清理日志、缓存和临时目录。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\Kingsoft\\*Cache*\\*",
            "%LOCALAPPDATA%\\Kingsoft\\*Cache*\\*",
            "%PROGRAMDATA%\\Kingsoft\\*log*\\*",
            "%LOCALAPPDATA%\\liebao\\*Cache*\\*",
            "%APPDATA%\\liebao\\*Cache*\\*",
        ),
        process_names=("kxetray.exe", "kxescore.exe", "liebao.exe"),
        service_keywords=("kingsoft", "kxes", "ksafe"),
        task_keywords=("kingsoft", "liebao", "ksafe"),
        registry_keywords=("kingsoft", "liebao", "ksafe"),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="pup.baidu_cache",
        title="百度系列软件缓存与日志",
        vendor="Baidu",
        category="已卸载软件残留",
        description="百度卫士、百度浏览器等软件卸载后留下的缓存、日志和临时文件。",
        safe_reason="只清理缓存、日志、临时目录。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\Baidu\\*Cache*\\*",
            "%LOCALAPPDATA%\\Baidu\\*Cache*\\*",
            "%PROGRAMDATA%\\Baidu\\*log*\\*",
            "%PROGRAMDATA%\\Baidu\\*temp*\\*",
        ),
        process_names=("BaiduSd.exe", "BaiduAnTray.exe", "BaiduBrowser.exe"),
        service_keywords=("baidu", "baidusd"),
        task_keywords=("baidu",),
        registry_keywords=("baidu",),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="pup.sogou_cache",
        title="搜狗浏览器/输入法缓存",
        vendor="Sogou",
        category="已卸载软件残留",
        description="搜狗浏览器、搜狗输入法卸载后留下的缓存、日志和升级文件。",
        safe_reason="不删除用户词库，只清理缓存、日志和临时升级包。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\SogouExplorer\\*Cache*\\*",
            "%LOCALAPPDATA%\\SogouExplorer\\*Cache*\\*",
            "%APPDATA%\\SogouPY\\*log*\\*",
            "%LOCALAPPDATA%\\SogouPY\\*temp*\\*",
        ),
        process_names=("SogouExplorer.exe", "SogouCloud.exe", "SogouInput.exe"),
        service_keywords=("sogou",),
        task_keywords=("sogou",),
        registry_keywords=("sogou", "sogouexplorer"),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="pup.2345_cache",
        title="2345 系列缓存与升级残留",
        vendor="2345",
        category="已卸载软件残留",
        description="2345 浏览器、看图王、好压、王牌输入法等软件卸载后留下的缓存、日志和升级文件。",
        safe_reason="只清理缓存、日志、临时安装包，不删除用户文件。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\2345*\\*Cache*\\*",
            "%LOCALAPPDATA%\\2345*\\*Cache*\\*",
            "%PROGRAMDATA%\\2345*\\*log*\\*",
            "%PROGRAMDATA%\\2345*\\*temp*\\*",
        ),
        process_names=("2345Explorer.exe", "2345Pic.exe", "2345SoftMgr.exe"),
        service_keywords=("2345",),
        task_keywords=("2345",),
        registry_keywords=("2345",),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="pup.compression_bundle_cache",
        title="压缩软件缓存与升级残留",
        vendor="压缩软件",
        category="已卸载软件残留",
        description="快压、万能压缩、好压等压缩工具卸载后留下的升级文件和缓存。",
        safe_reason="只清理缓存、日志和临时升级包。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\KuaiZip\\*",
            "%LOCALAPPDATA%\\KuaiZip\\*",
            "%APPDATA%\\Kuaizip\\*",
            "%LOCALAPPDATA%\\Kuaizip\\*",
            "%APPDATA%\\WanNeng*\\*Cache*\\*",
            "%LOCALAPPDATA%\\WanNeng*\\*Cache*\\*",
            "%APPDATA%\\2345HaoZip\\*Cache*\\*",
            "%LOCALAPPDATA%\\2345HaoZip\\*Cache*\\*",
        ),
        process_names=("kuaizip.exe", "wnzip.exe", "2345haozip.exe"),
        service_keywords=("kuaizip", "haozip", "wanneng"),
        task_keywords=("kuaizip", "haozip", "wanneng"),
        registry_keywords=("kuaizip", "haozip", "wanneng"),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="pup.news_wallpaper_gamebox_cache",
        title="资讯弹窗/壁纸/游戏盒子缓存",
        vendor="常见附属组件",
        category="已卸载软件残留",
        description="热点资讯、桌面壁纸、游戏大厅、软件管家类组件卸载后留下的缓存文件。",
        safe_reason="只清理缓存和日志，不移除用户主动安装的主程序。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\*Wallpaper*\\*Cache*\\*",
            "%LOCALAPPDATA%\\*Wallpaper*\\*Cache*\\*",
            "%APPDATA%\\*GameBox*\\*Cache*\\*",
            "%LOCALAPPDATA%\\*GameBox*\\*Cache*\\*",
            "%APPDATA%\\*News*\\*Cache*\\*",
            "%LOCALAPPDATA%\\*News*\\*Cache*\\*",
            "%PROGRAMDATA%\\*GameBox*\\*log*\\*",
        ),
        process_names=("gamebox.exe", "wallpaper.exe", "mininews.exe", "hotnews.exe"),
        service_keywords=("gamebox", "wallpaper", "hotnews", "mininews"),
        task_keywords=("gamebox", "wallpaper", "hotnews", "mininews"),
        registry_keywords=("gamebox", "wallpaper", "hotnews", "mininews"),
        default_selected=False,
    ),
    CleanupRule(
        rule_id="pup.international_adware",
        title="第三方工具栏/附加软件残留",
        vendor="第三方附加软件",
        category="已卸载软件残留",
        description="常见工具栏、浏览器辅助程序、附加软件卸载后留下的缓存和临时文件。",
        safe_reason="只清理缓存、日志和临时目录；不删除未知主程序。",
        risk=RiskLevel.MEDIUM,
        item_kind=ItemKind.DIRECTORY,
        path_patterns=(
            "%APPDATA%\\*Toolbar*\\*Cache*\\*",
            "%LOCALAPPDATA%\\*Toolbar*\\*Cache*\\*",
            "%APPDATA%\\*Adware*\\*Cache*\\*",
            "%LOCALAPPDATA%\\*Adware*\\*Cache*\\*",
            "%APPDATA%\\*Browser Assistant*\\*Cache*\\*",
            "%LOCALAPPDATA%\\*Browser Assistant*\\*Cache*\\*",
        ),
        process_names=("browserassistant.exe", "toolbar.exe", "adservice.exe"),
        service_keywords=("toolbar", "browser assistant", "adware"),
        task_keywords=("toolbar", "browser assistant", "adware"),
        registry_keywords=("toolbar", "browser assistant", "adware"),
        default_selected=False,
    ),
)


HIGH_RISK_INSPECTION_RULES: tuple[CleanupRule, ...] = (
    CleanupRule(
        rule_id="inspect.startup_items",
        title="高风险启动项检查",
        vendor="Windows",
        category="启动项管理",
        description="列出与已知软件关键词匹配的启动项。",
        safe_reason="启动项可能是用户需要的软件，首版只展示，不自动删除。",
        risk=RiskLevel.HIGH,
        item_kind=ItemKind.STARTUP,
        default_selected=False,
    ),
    CleanupRule(
        rule_id="inspect.services",
        title="高风险服务检查",
        vendor="Windows",
        category="服务检查",
        description="列出与已知软件关键词匹配的 Windows 服务。",
        safe_reason="服务删除可能导致软件或系统异常，首版只展示并建议官方卸载。",
        risk=RiskLevel.HIGH,
        item_kind=ItemKind.SERVICE,
        default_selected=False,
    ),
    CleanupRule(
        rule_id="inspect.scheduled_tasks",
        title="高风险计划任务检查",
        vendor="Windows",
        category="计划任务检查",
        description="列出与已知软件关键词匹配的计划任务。",
        safe_reason="计划任务可能承担更新或安全功能，首版只展示，不自动删除。",
        risk=RiskLevel.HIGH,
        item_kind=ItemKind.TASK,
        default_selected=False,
    ),
    CleanupRule(
        rule_id="inspect.registry",
        title="高风险注册表残留检查",
        vendor="Windows",
        category="注册表检查",
        description="提示可能存在的软件卸载项、启动项或残留键值。",
        safe_reason="注册表误删风险高，首版只提供人工核对说明。",
        risk=RiskLevel.HIGH,
        item_kind=ItemKind.REGISTRY,
        default_selected=False,
    ),
)


ALL_RULES: tuple[CleanupRule, ...] = (
    *SYSTEM_RULES,
    *BROWSER_RULES,
    *STUBBORN_SOFTWARE_RULES,
    *HIGH_RISK_INSPECTION_RULES,
)


PUP_KEYWORDS: tuple[str, ...] = tuple(
    sorted(
        {
            keyword.lower()
            for rule in STUBBORN_SOFTWARE_RULES
            for keyword in (
                *rule.service_keywords,
                *rule.task_keywords,
                *rule.registry_keywords,
                *rule.process_names,
            )
        }
    )
)


def get_rules() -> tuple[CleanupRule, ...]:
    return ALL_RULES


def get_cleanable_rules() -> tuple[CleanupRule, ...]:
    return tuple(rule for rule in ALL_RULES if rule.selectable and rule.path_patterns)


def get_inspection_rules() -> tuple[CleanupRule, ...]:
    return HIGH_RISK_INSPECTION_RULES
