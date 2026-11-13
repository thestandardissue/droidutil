#!/usr/bin/env python3
"""
DroidUtil - a WinUtil-style privacy & debloat utility for Android phones.

Runs on your computer (Windows / macOS / Linux) and talks to the phone over
ADB (USB or wireless debugging). No root needed. Everything it does can be undone.

    python droidutil.py

Requires Python 3.8+ with Tkinter (included in the python.org installers).
"""

import datetime
import hashlib
import json
import os
import platform
import queue
import re
import shutil
import stat
import subprocess
import sys
import threading
import urllib.request
import zipfile

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    from tkinter.scrolledtext import ScrolledText
except ImportError:  # pragma: no cover
    print("Tkinter is missing. Install Python from python.org (it includes Tkinter),\n"
          "or on Linux: sudo apt install python3-tk")
    sys.exit(1)

APP_NAME = "DroidUtil"
VERSION = "1.0"
DATA_DIR = os.path.join(os.path.expanduser("~"), ".droidutil")
PKG_RE = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$")
VALUE_RE = re.compile(r"^[A-Za-z0-9_.:/\-]+$")
NOWINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}

# ---------------------------------------------------------------------------
# Package database
#   risk: safe      -> "Recommended": bloat/telemetry, nothing you'll miss
#         optional  -> real apps; remove only if you don't use them
#         advanced  -> removes a system feature; read the note first
# ---------------------------------------------------------------------------
PACKAGES = {
    "Google": [
        ("com.google.android.videos", "Google TV / Play Movies", "safe", "Movie & TV store"),
        ("com.google.android.music", "Google Play Music", "safe", "Discontinued service"),
        ("com.google.android.apps.podcasts", "Google Podcasts", "safe", "Discontinued service"),
        ("com.google.android.apps.subscriptions.red", "Google One", "safe", "Subscription upsell"),
        ("com.google.android.apps.magazines", "Google News", "safe", ""),
        ("com.google.android.feedback", "Market Feedback Agent", "safe", "Sends feedback/crash reports for Play installs"),
        ("com.google.ar.core", "Google Play Services for AR", "safe", "Only needed by AR apps/games"),
        ("com.google.android.printservice.recommendation", "Print Service Recommendation", "safe", ""),
        ("com.google.android.apps.tachyon", "Google Meet (Duo)", "optional", "Video calling"),
        ("com.google.android.youtube", "YouTube", "optional", "Can use a browser instead"),
        ("com.google.android.apps.youtube.music", "YouTube Music", "optional", ""),
        ("com.google.android.apps.youtube.kids", "YouTube Kids", "optional", ""),
        ("com.google.android.apps.docs", "Google Drive", "optional", ""),
        ("com.google.android.apps.photos", "Google Photos", "optional", "Uploads your photos to Google if backup is on"),
        ("com.google.android.apps.maps", "Google Maps", "optional", ""),
        ("com.google.android.gm", "Gmail", "optional", ""),
        ("com.google.android.keep", "Google Keep", "optional", ""),
        ("com.google.android.calendar", "Google Calendar", "optional", "Install another calendar app first"),
        ("com.google.android.apps.fitness", "Google Fit", "optional", ""),
        ("com.google.android.apps.bard", "Gemini", "optional", "AI assistant app"),
        ("com.google.android.apps.googleassistant", "Google Assistant", "optional", ""),
        ("com.google.android.projection.gearhead", "Android Auto", "optional", "Only needed for car screens"),
        ("com.google.android.apps.chromecast.app", "Google Home", "optional", ""),
        ("com.google.android.apps.walletnfcrel", "Google Wallet", "optional", "Needed for tap-to-pay"),
        ("com.google.android.apps.adm", "Find My Device", "optional", "Privacy vs. anti-theft trade-off"),
        ("com.google.android.apps.nbu.files", "Files by Google", "optional", "Make sure you have another file manager"),
        ("com.google.android.marvin.talkback", "Android Accessibility Suite", "optional", "Keep if you use TalkBack/Select to Speak"),
        ("com.google.android.googlequicksearchbox", "Google app (Search/Discover)", "advanced",
         "Breaks Assistant, Discover and the Pixel Launcher search bar"),
        ("com.google.android.apps.wellbeing", "Digital Wellbeing", "advanced", "Removes screen time, bedtime & focus modes"),
        ("com.google.android.apps.turbo", "Device Health Services", "advanced", "Adaptive battery & battery estimates"),
        ("com.google.android.as", "Android System Intelligence", "advanced",
         "Live Caption, smart text selection, Now Playing"),
        ("com.google.android.apps.restore", "Data Restore Tool", "advanced", "Only used during phone setup"),
        ("com.android.chrome", "Chrome", "advanced",
         "Install another browser first. On Android 7-9 Chrome may provide WebView - removing breaks in-app web pages"),
    ],
    "Samsung": [
        ("com.samsung.android.bixby.agent", "Bixby Voice", "safe", ""),
        ("com.samsung.android.bixby.wakeup", "Bixby voice wake-up", "safe", "Always-listening hotword"),
        ("com.samsung.android.bixby.service", "Bixby features", "safe", ""),
        ("com.samsung.android.app.settings.bixby", "Bixby settings", "safe", ""),
        ("com.samsung.systemui.bixby2", "Bixby SystemUI plugin", "safe", ""),
        ("com.samsung.android.app.spage", "Samsung Free / Bixby Home", "safe", "Swipe-right news feed"),
        ("com.samsung.android.visionintelligence", "Bixby Vision", "safe", ""),
        ("com.samsung.android.arzone", "AR Zone", "safe", ""),
        ("com.samsung.android.aremoji", "AR Emoji", "safe", ""),
        ("com.samsung.android.ardrawing", "AR Doodle", "safe", ""),
        ("com.samsung.android.game.gamehome", "Game Launcher", "safe", ""),
        ("com.samsung.android.game.gametools", "Game Tools", "safe", ""),
        ("com.samsung.android.app.tips", "Samsung Tips", "safe", ""),
        ("com.samsung.android.mateagent", "Galaxy Friends", "safe", ""),
        ("com.samsung.android.voc", "Samsung Members", "safe", "Feedback & diagnostics app"),
        ("com.samsung.android.rubin.app", "Customization Service", "safe", "Profiles your usage for 'personalized' content"),
        ("com.samsung.android.ipsgeofence", "Visit In", "safe", "Location-based suggestions"),
        ("com.samsung.android.kidsinstaller", "Samsung Kids installer", "safe", ""),
        ("com.samsung.android.app.watchmanagerstub", "Galaxy Wearable stub", "safe", ""),
        ("com.samsung.android.stickercenter", "Sticker Center", "safe", ""),
        ("com.samsung.android.tvplus", "Samsung TV Plus", "safe", ""),
        ("com.samsung.android.svoiceime", "Samsung voice input", "safe", ""),
        ("com.sec.android.app.chromecustomizations", "Chrome customizations", "safe", "Vendor bookmarks for Chrome"),
        ("com.samsung.android.app.routines", "Modes and Routines", "optional", ""),
        ("com.samsung.android.oneconnect", "SmartThings", "optional", ""),
        ("com.samsung.android.smartmirroring", "Smart View", "optional", "Screen casting"),
        ("com.samsung.android.samsungpass", "Samsung Pass", "optional", ""),
        ("com.samsung.android.samsungpassautofill", "Samsung Pass autofill", "optional", ""),
        ("com.samsung.android.spay", "Samsung Wallet / Pay", "optional", ""),
        ("com.sec.android.app.sbrowser", "Samsung Internet", "optional", "Install another browser first"),
        ("com.samsung.android.email.provider", "Samsung Email", "optional", ""),
        ("com.samsung.android.app.sharelive", "Quick Share", "optional", ""),
        ("com.samsung.android.bixbyvision.framework", "Bixby Vision framework", "advanced", "Some camera features (QR, scene) may stop"),
        ("com.samsung.android.game.gos", "Game Optimizing Service", "advanced", "Controls throttling/thermals in games"),
        ("com.sec.android.diagmonagent", "DiagMonAgent", "advanced", "Diagnostics/telemetry uploader"),
        ("com.samsung.android.scloud", "Samsung Cloud", "advanced", "Backup/sync with Samsung account"),
        ("com.samsung.android.forest", "Digital Wellbeing (Samsung)", "advanced", ""),
        ("com.samsung.android.da.daagent", "Dual Messenger", "advanced", "Breaks cloned apps"),
        ("com.sec.android.app.samsungapps", "Galaxy Store", "advanced", "Updates some Samsung apps (Good Lock etc.)"),
    ],
    "Xiaomi / Redmi / POCO": [
        ("com.miui.analytics", "MIUI Analytics", "safe", "Telemetry"),
        ("com.miui.msa.global", "MSA (system ads)", "safe", "Shows ads inside system apps"),
        ("com.miui.hybrid", "Quick Apps", "safe", ""),
        ("com.miui.hybrid.accessory", "Quick Apps accessory", "safe", ""),
        ("com.miui.yellowpage", "Yellow Pages", "safe", ""),
        ("com.xiaomi.glgm", "Xiaomi Games", "safe", ""),
        ("com.xiaomi.mipicks", "GetApps", "safe", "Xiaomi app store with ads"),
        ("com.xiaomi.discover", "System App Updater", "safe", ""),
        ("com.miui.bugreport", "Bug report", "safe", ""),
        ("com.miui.android.fashiongallery", "Wallpaper Carousel", "safe", ""),
        ("com.mi.android.globalminusscreen", "App Vault", "safe", "Swipe-left feed"),
        ("com.mi.globalbrowser", "Mi Browser", "optional", "Install another browser first"),
        ("com.miui.videoplayer", "Mi Video", "optional", ""),
        ("com.miui.player", "Mi Music", "optional", ""),
        ("com.mipay.wallet.in", "Mi Pay", "optional", ""),
        ("com.miui.weather2", "Weather", "optional", ""),
        ("com.miui.notes", "Notes", "optional", ""),
        ("com.miui.compass", "Compass", "optional", ""),
        ("com.miui.fm", "FM Radio", "optional", ""),
        ("com.xiaomi.midrop", "ShareMe", "optional", ""),
        ("com.miui.daemon", "MIUI Daemon", "advanced", "Collects device stats"),
        ("com.xiaomi.joyose", "Joyose", "advanced", "Performance/thermal profiles + cloud config"),
    ],
    "OnePlus / OPPO / Realme": [
        ("com.heytap.market", "App Market", "safe", "Store with promoted apps"),
        ("com.oppo.market", "OPPO App Market", "safe", ""),
        ("com.heytap.pictorial", "Lock screen magazine", "safe", ""),
        ("com.heytap.browser", "Browser", "optional", "Install another browser first"),
        ("com.heytap.cloud", "HeyTap Cloud", "optional", ""),
        ("com.heytap.music", "Music", "optional", ""),
        ("com.coloros.gamespaceui", "Game Space", "optional", ""),
        ("com.oneplus.brickmode", "Zen Mode", "optional", ""),
        ("com.nearme.statistics.rom", "Usage statistics", "advanced", "Telemetry"),
        ("com.oplus.statistics.rom", "Usage statistics", "advanced", "Telemetry"),
    ],
    "Motorola": [
        ("com.motorola.help", "Moto Help", "safe", ""),
        ("com.motorola.genie", "Device Help", "safe", ""),
        ("com.motorola.demo", "Demo mode", "safe", ""),
        ("com.motorola.gamemode", "Game Time", "optional", ""),
        ("com.motorola.moto", "Moto app", "optional", "Gestures (chop for flashlight etc.) live here"),
        ("com.motorola.ccc.notification", "Motorola Notifications", "advanced", "Promotional & update notices"),
    ],
    "Pre-installed 3rd party & carrier": [
        ("com.facebook.appmanager", "Facebook App Manager", "safe", "Background updater"),
        ("com.facebook.services", "Facebook Services", "safe", "Background service"),
        ("com.facebook.system", "Facebook App Installer", "safe", ""),
        ("com.facebook.katana", "Facebook", "safe", "Pre-installed copy"),
        ("com.linkedin.android", "LinkedIn", "safe", ""),
        ("com.netflix.partner.activation", "Netflix activation", "safe", ""),
        ("com.amazon.appmanager", "Amazon App Manager", "safe", ""),
        ("com.booking", "Booking.com", "safe", ""),
        ("com.LogiaGroup.LogiaDeck", "DT Ignite / LogiaDeck", "safe", "Installs sponsored apps"),
        ("com.aura.oobe.samsung", "AppCloud (ironSource)", "safe", "Pushes sponsored apps"),
        ("com.aura.oobe.samsung.gl", "AppCloud (ironSource)", "safe", "Pushes sponsored apps"),
        ("com.microsoft.skydrive", "OneDrive", "optional", ""),
        ("com.microsoft.office.officehubrow", "Microsoft 365 (Office)", "optional", ""),
        ("com.netflix.mediaclient", "Netflix", "optional", ""),
        ("com.spotify.music", "Spotify", "optional", ""),
        ("com.amazon.mShop.android.shopping", "Amazon Shopping", "optional", ""),
        ("com.instagram.android", "Instagram", "optional", ""),
        ("com.vzw.hss.myverizon", "My Verizon", "optional", ""),
        ("com.tmobile.pr.mytmobile", "T-Mobile / T-Life", "optional", ""),
        ("com.att.myWireless", "myAT&T", "optional", ""),
    ],
}

VENDOR_GROUPS = {
    "samsung": "Samsung",
    "xiaomi": "Xiaomi / Redmi / POCO", "redmi": "Xiaomi / Redmi / POCO", "poco": "Xiaomi / Redmi / POCO",
    "oneplus": "OnePlus / OPPO / Realme", "oppo": "OnePlus / OPPO / Realme", "realme": "OnePlus / OPPO / Realme",
    "motorola": "Motorola", "lenovo": "Motorola",
}

# Never offered for removal - doing so can bootloop the phone, lock you out or kill ADB itself.
PROTECTED = {
    "android", "com.android.systemui", "com.android.settings", "com.android.phone", "com.android.shell",
    "com.android.server.telecom", "com.android.bluetooth", "com.android.nfc", "com.android.se",
    "com.android.keychain", "com.android.externalstorage", "com.android.location.fused",
    "com.android.packageinstaller", "com.google.android.packageinstaller",
    "com.android.permissioncontroller", "com.google.android.permissioncontroller",
    "com.google.android.gms", "com.google.android.gsf", "com.android.vending",
    "com.android.launcher3", "com.google.android.apps.nexuslauncher", "com.sec.android.app.launcher", "com.miui.home",
    "com.android.inputmethod.latin", "com.google.android.inputmethod.latin", "com.samsung.android.honeyboard",
    "com.miui.securitycenter", "com.lbe.security.miui", "com.xiaomi.finddevice", "com.samsung.android.kgclient",
    "com.android.providers.settings", "com.android.providers.telephony", "com.android.providers.media",
    "com.android.providers.contacts", "com.android.providers.downloads",
}
PROTECTED_PREFIXES = ("com.android.providers.", "com.android.networkstack", "com.google.android.networkstack",
                      "com.android.wifi", "com.google.android.wifi", "com.android.cellbroadcast",
                      "com.google.android.cellbroadcast", "com.android.ims", "com.qualcomm.qti.")


def _check(ok):
    if not ok:
        raise ValueError("refused: unsafe package name, protected package or bad value")


def is_protected(pkg):
    return pkg in PROTECTED or pkg.startswith(PROTECTED_PREFIXES)


RISK_LABEL = {"safe": "Recommended", "optional": "Optional", "advanced": "Advanced", "unknown": "Unknown"}

# ---------------------------------------------------------------------------
# Privacy tweaks: (id, title, description, [(namespace, key, value)], checked by default)
# ---------------------------------------------------------------------------
TWEAKS = [
    ("wifi_scan", "Turn off Wi-Fi scanning",
     "Stops apps and location services scanning for Wi-Fi networks while Wi-Fi is switched off.",
     [("global", "wifi_scan_always_enabled", "0")], True),
    ("ble_scan", "Turn off Bluetooth scanning",
     "Stops apps and location services scanning for Bluetooth devices while Bluetooth is off.",
     [("global", "ble_scan_always_enabled", "0")], True),
    ("lock_private", "Hide notification content on the lock screen",
     "Shows that you have a message, but not who it's from or what it says, until unlocked.",
     [("secure", "lock_screen_allow_private_notifications", "0")], True),
    ("show_pw", "Don't flash password characters while typing",
     "Stops the last typed character being shown in password fields (shoulder-surfing / screen recording).",
     [("system", "show_password", "0")], True),
    ("netrec", "Turn off network recommendations",
     "Stops the network-rating service scoring Wi-Fi networks and auto-connecting to open ones.",
     [("global", "network_recommendations_enabled", "0")], False),
    ("lock_none", "Hide ALL notifications on the lock screen",
     "Stricter version of the above: nothing shows until you unlock.",
     [("secure", "lock_screen_show_notifications", "0")], False),
    ("captive", "Disable connectivity checks (stops pinging Google)",
     "Android contacts Google every time it joins a network, even with a VPN. Turning this off stops that, "
     "BUT hotel/airport Wi-Fi sign-in pages won't pop up and 'no internet' warnings stop working.",
     [("global", "captive_portal_mode", "0")], False),
]

# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------
ANIM_KEYS = ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")
ANIM_CHOICES = [("Leave unchanged", None), ("Fast (0.5x) - recommended", "0.5"),
                ("Off (instant, can feel abrupt)", "0"), ("Normal (1x, Android default)", "1")]

# (id, title, description, [(namespace, key, value)], checked by default)
#  value "__maxhz__" is replaced by the phone's highest supported refresh rate.
PERF_TWEAKS = [
    ("freezer", "Freeze cached background apps",
     "Apps sitting in the background stop using CPU and battery until you open them again "
     "(Android 11+; takes effect after a reboot). Many newer phones already do this.",
     [("global", "cached_apps_freezer", "enabled")], True),
    ("refresh", "Keep the screen at its highest refresh rate",
     "Smoother scrolling all the time, but uses more battery. Works on Pixel and many others; "
     "Samsung ignores it - use Settings > Display > Motion smoothness instead.",
     [("system", "peak_refresh_rate", "__maxhz__"), ("system", "min_refresh_rate", "__maxhz__")], False),
]

# (button label, shell command, explanation, timeout seconds)
PERF_ACTIONS = [
    ("Optimize (compile) all apps now",
     "cmd package bg-dexopt-job",
     "Runs the app optimization Android normally does overnight while charging. Apps open faster - "
     "especially after a system update. Can take 5-20 minutes; keep the phone plugged in.", 1800),
    ("Clear all app caches",
     "pm trim-caches 999G",
     "Deletes temporary cache files of every app to free storage. Nothing personal is deleted; "
     "apps rebuild what they need.", 300),
    ("Close all background apps",
     "am kill-all",
     "Stops apps running in the background to free RAM right now (like a one-time 'clear all').", 60),
]

DNS_PROVIDERS = [
    ("Leave unchanged", None),
    ("AdGuard - blocks ads & trackers", "dns.adguard-dns.com"),
    ("Mullvad - blocks ads & trackers", "adblock.dns.mullvad.net"),
    ("Quad9 - blocks malware", "dns.quad9.net"),
    ("Mullvad - no filtering", "dns.mullvad.net"),
    ("Cloudflare - no filtering", "one.one.one.one"),
    ("Automatic (Android default)", "__auto__"),
    ("Off", "__off__"),
    ("Custom hostname...", "__custom__"),
]

SETTINGS_SHORTCUTS = [
    ("Privacy settings", "android.settings.PRIVACY_SETTINGS"),
    ("Permission manager", "android.intent.action.MANAGE_PERMISSIONS"),
    ("Location settings", "android.settings.LOCATION_SOURCE_SETTINGS"),
    ("Google Ads ID (delete it)", "com.google.android.gms.settings.ADS_PRIVACY"),
    ("Apps with usage access", "android.settings.USAGE_ACCESS_SETTINGS"),
    ("Install unknown apps", "android.settings.MANAGE_UNKNOWN_APP_SOURCES"),
    ("Security settings", "android.settings.SECURITY_SETTINGS"),
]

# ---------------------------------------------------------------------------
# Curated open-source apps: (category, name, package, source, description, starter-pack)
#   source "fdroid"  -> latest build from f-droid.org (right CPU type picked automatically)
#   source "signal"  -> official APK from signal.org, SHA-256 checked
#   source "https://..." -> developer's official direct APK link
# ---------------------------------------------------------------------------
APPS = [
    ("App stores", "F-Droid", "org.fdroid.fdroid", "fdroid",
     "Store with only open-source apps. Keeps the F-Droid apps below updated.", True),
    ("App stores", "Obtainium", "dev.imranr.obtainium.fdroid", "fdroid",
     "Gets updates straight from developers' GitHub/GitLab releases.", True),
    ("App stores", "Droid-ify", "com.looker.droidify", "fdroid", "Faster, modern F-Droid client.", False),
    ("App stores", "Aurora Store", "com.aurora.store", "fdroid",
     "Download Play Store apps anonymously, without a Google account.", False),
    ("VPN & Tor", "Mullvad VPN", "net.mullvad.mullvadvpn", "fdroid",
     "Paid VPN, no email or account info needed. Strong privacy reputation.", True),
    ("VPN & Tor", "Proton VPN", "ch.protonvpn.android", "fdroid",
     "Swiss VPN with a free tier (no ads, no data limit).", True),
    ("VPN & Tor", "IVPN", "net.ivpn.client", "fdroid", "Paid VPN, anonymous accounts, audited no-logs.", False),
    ("VPN & Tor", "WireGuard", "com.wireguard.android", "fdroid",
     "Official WireGuard client - for your own VPN server or provider configs.", False),
    ("VPN & Tor", "Orbot", "org.torproject.android",
     "https://guardianproject.info/releases/orbot-latest.apk",
     "Routes apps through the Tor network (official Guardian Project build).", False),
    ("Firewall & ad blocking", "RethinkDNS", "com.celzero.bravedns", "fdroid",
     "Firewall + tracker-blocking DNS per app. No root.", True),
    ("Firewall & ad blocking", "TrackerControl", "net.kollnig.missioncontrol.fdroid", "fdroid",
     "Shows and blocks the trackers each app contacts.", False),
    ("Firewall & ad blocking", "NetGuard", "eu.faircode.netguard", "fdroid",
     "Simple per-app internet on/off firewall.", False),
    ("Browsers", "DuckDuckGo Browser", "com.duckduckgo.mobile.android", "fdroid",
     "Blocks trackers, one-tap 'burn' of all tabs and data.", False),
    ("Browsers", "Fennec", "org.mozilla.fennec_fdroid", "fdroid",
     "Firefox without Mozilla telemetry. Supports uBlock Origin.", True),
    ("Messaging", "Signal", "org.thoughtcrime.securesms", "signal",
     "End-to-end encrypted messaging and calls (official build from signal.org).", True),
    ("Messaging", "Element", "im.vector.app", "fdroid", "Encrypted chat on the decentralised Matrix network.", False),
    ("Messaging", "Briar", "org.briarproject.briar.android", "fdroid",
     "Peer-to-peer messenger; works over Tor, Wi-Fi or Bluetooth.", False),
    ("Passwords & 2FA", "KeePassDX", "com.kunzisoft.keepass.libre", "fdroid",
     "Offline password manager (KeePass files).", False),
    ("Passwords & 2FA", "Aegis Authenticator", "com.beemdevelopment.aegis", "fdroid",
     "Encrypted 2FA codes - replaces Google Authenticator.", True),
    ("Passwords & 2FA", "Ente Auth", "io.ente.auth", "fdroid", "2FA codes with optional encrypted sync.", False),
    ("Email", "Thunderbird", "net.thunderbird.android", "fdroid", "Open-source email (formerly K-9 Mail).", False),
    ("Email", "FairEmail", "eu.faircode.email", "fdroid", "Privacy-focused email; blocks tracking images.", False),
    ("Everyday apps", "HeliBoard", "helium314.keyboard", "fdroid",
     "Keyboard with no internet access - nothing you type leaves the phone.", True),
    ("Everyday apps", "Organic Maps", "app.organicmaps", "fdroid", "Offline maps & navigation, no tracking.", False),
    ("Everyday apps", "NewPipe", "org.schabi.newpipe", "fdroid", "YouTube without ads, tracking or account.", False),
    ("Everyday apps", "Fossify Gallery", "org.fossify.gallery", "fdroid", "Offline photo gallery.", False),
    ("Everyday apps", "Fossify File Manager", "org.fossify.filemanager", "fdroid", "Offline file manager.", False),
    ("Privacy tools", "Exodus Privacy", "org.eu.exodus_privacy.exodusp", "fdroid",
     "Shows trackers and permissions in every app you have.", False),
    ("Privacy tools", "App Manager", "io.github.muntashirakon.AppManager", "fdroid",
     "Powerful app inspector: trackers, permissions, components.", False),
]
USER_AGENT = f"{APP_NAME}/{VERSION}"


def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def resolve_apk(pkg, source, abis=()):
    """Return a list of download candidates [(url, sha256 or None)], best first."""
    if source == "fdroid":
        data = json.loads(http_get(f"https://f-droid.org/api/v1/packages/{pkg}"))
        best = data["suggestedVersionCode"]
        versions = data.get("packages", [])
        name = next((v["versionName"] for v in versions if v["versionCode"] == best), None)
        # Same version, other CPU-type builds as fallbacks (F-Droid publishes one APK per ABI for some apps)
        codes = [best] + sorted({v["versionCode"] for v in versions
                                 if v["versionName"] == name and v["versionCode"] != best}, reverse=True)
        return [(f"https://f-droid.org/repo/{pkg}_{vc}.apk", None) for vc in codes]
    if source == "signal":
        data = json.loads(http_get("https://updates.signal.org/android/latest.json"))
        return [(data["url"], data.get("sha256sum"))]
    if source.startswith("https://"):
        return [(source, None)]
    raise ValueError(f"unknown source {source}")


def download_apk(url, sha256=None):
    folder = os.path.join(DATA_DIR, "apks")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, re.sub(r"[^A-Za-z0-9_.-]", "_", url.rsplit("/", 1)[-1]) or "app.apk")
    data = http_get(url, timeout=600)
    if sha256 and hashlib.sha256(data).hexdigest().lower() != sha256.lower():
        raise ValueError("checksum mismatch - download corrupted or tampered with, not installing")
    with open(path, "wb") as f:
        f.write(data)
    return path


SENSITIVE_PERMS = {
    "android.permission.ACCESS_FINE_LOCATION": "Precise location",
    "android.permission.ACCESS_COARSE_LOCATION": "Approximate location",
    "android.permission.ACCESS_BACKGROUND_LOCATION": "Location in background",
    "android.permission.CAMERA": "Camera",
    "android.permission.RECORD_AUDIO": "Microphone",
    "android.permission.READ_CONTACTS": "Read contacts",
    "android.permission.WRITE_CONTACTS": "Edit contacts",
    "android.permission.READ_CALL_LOG": "Read call log",
    "android.permission.READ_SMS": "Read SMS",
    "android.permission.RECEIVE_SMS": "Receive SMS",
    "android.permission.SEND_SMS": "Send SMS",
    "android.permission.READ_CALENDAR": "Read calendar",
    "android.permission.BODY_SENSORS": "Body sensors",
    "android.permission.ACTIVITY_RECOGNITION": "Physical activity",
    "android.permission.READ_PHONE_STATE": "Phone state / IDs",
    "android.permission.READ_PHONE_NUMBERS": "Phone number",
    "android.permission.READ_MEDIA_IMAGES": "Photos",
    "android.permission.READ_MEDIA_VIDEO": "Videos",
    "android.permission.READ_EXTERNAL_STORAGE": "Storage (files & media)",
    "android.permission.NEARBY_WIFI_DEVICES": "Nearby Wi-Fi devices",
    "android.permission.BLUETOOTH_SCAN": "Nearby Bluetooth devices",
}


# ---------------------------------------------------------------------------
# ADB layer (no GUI code here)
# ---------------------------------------------------------------------------
def find_adb():
    override = os.environ.get("DROIDUTIL_ADB")
    if override:
        return override
    exe = "adb.exe" if os.name == "nt" else "adb"
    local = os.path.join(DATA_DIR, "platform-tools", exe)
    if os.path.isfile(local):
        return local
    return shutil.which("adb")


def download_adb(log):
    system = {"Windows": "windows", "Darwin": "darwin"}.get(platform.system(), "linux")
    url = f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip"
    os.makedirs(DATA_DIR, exist_ok=True)
    zpath = os.path.join(DATA_DIR, "platform-tools.zip")
    log(f"Downloading {url}")
    urllib.request.urlretrieve(url, zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(DATA_DIR)
    os.remove(zpath)
    adb = os.path.join(DATA_DIR, "platform-tools", "adb.exe" if os.name == "nt" else "adb")
    if os.name != "nt":
        os.chmod(adb, os.stat(adb).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    log(f"ADB installed to {adb}")
    return adb


class Adb:
    def __init__(self, path, log):
        self.path = path
        self.log = log
        self.serial = None
        self.dry_run = False

    def run(self, args, device=True, timeout=90):
        cmd = [self.path] + (["-s", self.serial] if device and self.serial else []) + list(args)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, **NOWINDOW)
            return p.returncode, (p.stdout + p.stderr).strip()
        except subprocess.TimeoutExpired:
            return 1, "timed out"
        except OSError as e:
            return 1, str(e)

    def shell(self, cmd, change=False, timeout=90):
        """Run a shell command on the phone. change=True marks commands that modify the phone."""
        if change:
            self.log(("[dry run] " if self.dry_run else "> ") + cmd)
            if self.dry_run:
                return 0, "Success"
        rc, out = self.run(["shell", cmd], timeout=timeout)
        if change and out:
            self.log("  " + out.replace("\n", "\n  "))
        return rc, out

    # --- device ---
    def devices(self):
        rc, out = self.run(["devices", "-l"], device=False)
        result = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and not line.startswith("*"):
                model = next((p.split(":", 1)[1] for p in parts if p.startswith("model:")), "")
                result.append((parts[0], parts[1], model.replace("_", " ")))
        return result

    def prop(self, key):
        return self.shell(f"getprop {key}")[1].strip()

    def info(self):
        sdk = self.prop("ro.build.version.sdk")
        return {
            "manufacturer": self.prop("ro.product.manufacturer"),
            "brand": self.prop("ro.product.brand"),
            "model": self.prop("ro.product.model"),
            "android": self.prop("ro.build.version.release"),
            "sdk": int(sdk) if sdk.isdigit() else 0,
        }

    # --- packages ---
    def packages(self, flags=""):
        out = self.shell(f"pm list packages {flags}".strip())[1]
        return {l.split(":", 1)[1].strip() for l in out.splitlines() if l.startswith("package:")}

    def package_state(self):
        installed = self.packages()
        return {
            "installed": installed,
            "disabled": self.packages("-d"),
            "removed": self.packages("-u") - installed,
            "user": self.packages("-3"),
        }

    def uninstall(self, pkg):
        """Remove pkg for the main user. Returns the action that took effect:
        "uninstall", "disable" (fallback for blocked system apps), or None on failure."""
        _check(PKG_RE.match(pkg) and not is_protected(pkg))
        out = self.shell(f"pm uninstall -k --user 0 {pkg}", change=True)[1]
        if "Success" in out:
            return "uninstall"
        # Newer Android (seen on Android 17) refuses per-user uninstall of built-in
        # system apps from ADB without root. Disabling still works and is reversible.
        if "only root can delete system app" in out:
            self.log(f"  Android blocks uninstalling built-in system apps without root - disabling {pkg} instead.")
            return "disable" if self.disable(pkg) else None
        return None

    def disable(self, pkg):
        _check(PKG_RE.match(pkg) and not is_protected(pkg))
        out = self.shell(f"pm disable-user --user 0 {pkg}", change=True)[1]
        return self.dry_run or "disabled" in out

    def restore(self, pkg):
        _check(PKG_RE.match(pkg))
        out = self.shell(f"cmd package install-existing --user 0 {pkg}", change=True)[1]
        if self.dry_run or "installed for user" in out:
            return True
        out = self.shell(f"pm install-existing --user 0 {pkg}", change=True)[1]
        return "installed for user" in out

    def enable(self, pkg):
        _check(PKG_RE.match(pkg))
        out = self.shell(f"pm enable --user 0 {pkg}", change=True)[1]
        return self.dry_run or "enabled" in out

    # --- settings ---
    def get_setting(self, ns, key):
        v = self.shell(f"settings get {ns} {key}")[1].strip()
        return None if v in ("null", "") else v

    def put_setting(self, ns, key, value):
        _check(ns in ("global", "secure", "system") and VALUE_RE.match(key))
        if value is None:
            self.shell(f"settings delete {ns} {key}", change=True)
            return True
        _check(VALUE_RE.match(value))
        self.shell(f"settings put {ns} {key} {value}", change=True)
        if self.dry_run:
            return True
        return self.get_setting(ns, key) == value

    # --- permissions ---
    def granted_sensitive(self, pkg):
        out = self.shell(f"dumpsys package {pkg}")[1]
        found = set(re.findall(r"(android\.permission\.[A-Z_]+): granted=true", out))
        return sorted(p for p in found if p in SENSITIVE_PERMS)

    def revoke(self, pkg, perm):
        _check(PKG_RE.match(pkg) and perm in SENSITIVE_PERMS)
        rc, out = self.shell(f"pm revoke {pkg} {perm}", change=True)
        return self.dry_run or (rc == 0 and "Exception" not in out and "rror" not in out)

    def max_refresh_rate(self):
        out = self.shell("dumpsys display")[1]
        rates = [float(x) for x in re.findall(r"(?:fps|refreshRate)=([0-9]+(?:\.[0-9]+)?)", out)]
        rates = [r for r in rates if 30 <= r <= 240]
        return f"{max(rates):.1f}" if rates else None

    def install_apk(self, path):
        """Returns (ok, message)."""
        self.log(("[dry run] " if self.dry_run else "> ") + f"adb install -r {os.path.basename(path)}")
        if self.dry_run:
            return True, "Success"
        rc, out = self.run(["install", "-r", path], timeout=900)
        last = out.strip().splitlines()[-1] if out.strip() else "no output"
        self.log("  " + last)
        return "Success" in out, out

    def open_settings(self, action):
        return self.shell(f"am start -a {action}", change=True)


class Backup:
    """Remembers original setting values + what was removed, per phone, so everything can be undone."""

    def __init__(self, serial):
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", serial)
        os.makedirs(DATA_DIR, exist_ok=True)
        self.path = os.path.join(DATA_DIR, f"backup_{safe}.json")
        self.data = {"settings": {}, "history": []}
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except (OSError, ValueError):
                pass

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def remember_setting(self, ns, key, original):
        k = f"{ns}/{key}"
        if k not in self.data["settings"]:  # keep the very first (factory) value
            self.data["settings"][k] = original
            self.save()

    def add(self, action, target):
        self.data["history"].append({"time": datetime.datetime.now().isoformat(timespec="seconds"),
                                     "action": action, "target": target})
        self.save()


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class CheckTree(ttk.Frame):
    """Treeview with a clickable checkbox column."""

    def __init__(self, master, columns, widths, height=15):
        super().__init__(master)
        self.checked = set()
        self.tree = ttk.Treeview(self, columns=("sel",) + tuple(columns), show="headings",
                                 selectmode="none", height=height)
        self.tree.heading("sel", text="")
        self.tree.column("sel", width=34, stretch=False, anchor="center")
        for c, w in zip(columns, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, stretch=(w > 200), anchor="w")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self._click)
        self.tree.bind("<space>", lambda e: None)
        for tag, color in (("safe", "#1b7f3b"), ("optional", "#1f5fa8"), ("advanced", "#b45f06"),
                           ("unknown", "#b00020"), ("muted", "#8a8a8a")):
            self.tree.tag_configure(tag, foreground=color)

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self.checked.clear()

    def add(self, iid, values, tag=None, checkable=True):
        self.tree.insert("", "end", iid=iid, values=("☐" if checkable else "",) + tuple(values),
                         tags=(tag,) if tag else ())

    def _click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        iid = self.tree.identify_row(event.y)
        if iid:
            self.toggle(iid)

    def toggle(self, iid, state=None):
        vals = list(self.tree.item(iid, "values"))
        if not vals or vals[0] == "":
            return
        on = (iid not in self.checked) if state is None else state
        (self.checked.add if on else self.checked.discard)(iid)
        vals[0] = "☑" if on else "☐"
        self.tree.item(iid, values=vals)

    def set_all(self, predicate):
        for iid in self.tree.get_children():
            self.toggle(iid, bool(predicate(iid)))


class App:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_NAME} {VERSION} - Android privacy & debloat")
        root.geometry("1120x780")
        root.minsize(920, 620)
        self.q = queue.Queue()
        self.busy = False
        self.adb = None
        self.info = {}
        self.state = {"installed": set(), "disabled": set(), "removed": set(), "user": set()}
        self.backup = None
        self.devices = []

        style = ttk.Style()
        if "clam" in style.theme_names() and platform.system() == "Linux":
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("TkDefaultFont", 13, "bold"))
        style.configure("Accent.TButton", font=("TkDefaultFont", 10, "bold"))

        paned = ttk.PanedWindow(root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        self.nb = ttk.Notebook(paned)
        paned.add(self.nb, weight=5)
        logframe = ttk.LabelFrame(paned, text="Log", padding=4)
        paned.add(logframe, weight=1)
        self.logbox = ScrolledText(logframe, height=7, state="disabled", font=("Courier", 9), wrap="word")
        self.logbox.pack(fill="both", expand=True)

        bar = ttk.Frame(root, padding=(8, 4))
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text="Starting...")
        self.status.pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=160)
        self.progress.pack(side="right")

        self._tab_connect()
        self._tab_debloat()
        self._tab_tweaks()
        self._tab_performance()
        self._tab_install()
        self._tab_permissions()
        self._tab_restore()

        root.after(100, self._poll)
        root.after(300, self.init_adb)

    # ----- plumbing -----
    def log(self, msg):
        self.q.put(("log", msg))

    def ui(self, fn):
        self.q.put(("call", fn))

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.logbox.configure(state="normal")
                    self.logbox.insert("end", payload + "\n")
                    self.logbox.see("end")
                    self.logbox.configure(state="disabled")
                else:
                    payload()
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def run_bg(self, label, fn, done=None):
        if self.busy:
            messagebox.showinfo(APP_NAME, "Still working on the previous task - give it a moment.")
            return
        self.busy = True
        self.status.configure(text=label + "...")
        self.progress.start(12)

        def worker():
            result = None
            try:
                result = fn()
            except Exception as e:  # keep the UI alive no matter what
                self.log(f"ERROR: {e}")
            def finish():
                self.busy = False
                self.progress.stop()
                self.status.configure(text=self._status_text())
                if done:
                    done(result)
            self.ui(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _status_text(self):
        if not self.adb:
            return "ADB not found - see the Connect tab"
        if not self.adb.serial:
            return "No phone connected"
        i = self.info
        dry = "   [DRY RUN - nothing will be changed]" if self.adb.dry_run else ""
        return f"Connected: {i.get('brand', '').title()} {i.get('model', '')} - Android {i.get('android', '?')}{dry}"

    def need_device(self):
        if not self.adb or not self.adb.serial:
            messagebox.showwarning(APP_NAME, "Connect a phone first (Connect tab).")
            return False
        return True

    # ----- tab 1: connect -----
    def _tab_connect(self):
        f = ttk.Frame(self.nb, padding=14)
        self.nb.add(f, text="  1. Connect  ")
        ttk.Label(f, text="Connect your phone", style="Title.TLabel").pack(anchor="w")

        box = ttk.LabelFrame(f, text="ADB (Android Debug Bridge)", padding=10)
        box.pack(fill="x", pady=(10, 6))
        self.adb_label = ttk.Label(box, text="Looking for ADB...")
        self.adb_label.pack(side="left")
        ttk.Button(box, text="Download ADB from Google", command=self.on_download_adb).pack(side="right")

        box = ttk.LabelFrame(f, text="Phone", padding=10)
        box.pack(fill="x", pady=6)
        row = ttk.Frame(box)
        row.pack(fill="x")
        self.dev_combo = ttk.Combobox(row, state="readonly", width=60)
        self.dev_combo.pack(side="left")
        self.dev_combo.bind("<<ComboboxSelected>>", lambda e: self.select_device())
        ttk.Button(row, text="Refresh", command=self.refresh_devices).pack(side="left", padx=6)
        self.dry_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Dry run (only show what would happen)", variable=self.dry_var,
                        command=self.on_dry).pack(side="right")
        self.dev_label = ttk.Label(box, text="", foreground="#444")
        self.dev_label.pack(anchor="w", pady=(8, 0))

        box = ttk.LabelFrame(f, text="Wireless debugging (Android 11+, no cable needed)", padding=10)
        box.pack(fill="x", pady=6)
        r1 = ttk.Frame(box)
        r1.pack(fill="x")
        ttk.Label(r1, text="Pairing IP:port").pack(side="left")
        self.pair_addr = ttk.Entry(r1, width=22)
        self.pair_addr.pack(side="left", padx=4)
        ttk.Label(r1, text="Pairing code").pack(side="left")
        self.pair_code = ttk.Entry(r1, width=10)
        self.pair_code.pack(side="left", padx=4)
        ttk.Button(r1, text="Pair", command=self.on_pair).pack(side="left", padx=4)
        ttk.Label(r1, text="   then  Connect IP:port").pack(side="left")
        self.conn_addr = ttk.Entry(r1, width=22)
        self.conn_addr.pack(side="left", padx=4)
        ttk.Button(r1, text="Connect", command=self.on_connect).pack(side="left")

        help_text = (
            "How to get your phone ready (one time):\n"
            "  1. Settings > About phone > tap 'Build number' 7 times (Xiaomi: 'MIUI/OS version'; Samsung: Software information).\n"
            "  2. Settings > System > Developer options > turn on 'USB debugging'.\n"
            "        Xiaomi also: turn on 'USB debugging (Security settings)'.\n"
            "  3. Plug in with a data USB cable, tap 'Allow' on the phone's prompt (tick 'Always allow'), then press Refresh.\n"
            "        Windows: if the phone isn't listed, install your phone maker's USB driver (Samsung/Google USB driver).\n\n"
            "Wireless: Developer options > Wireless debugging > 'Pair device with pairing code' - type the IP:port and code\n"
            "shown there into the boxes above, press Pair, then put the IP:port from the main Wireless debugging screen into Connect.\n\n"
            "Then work through the tabs left to right. Tip: try Dry run first to preview every command.\n"
            "When you're done, turn USB debugging back off (button on the Privacy tweaks tab)."
        )
        ttk.Label(f, text=help_text, justify="left").pack(anchor="w", pady=(10, 0))

    def init_adb(self):
        path = find_adb()
        if path:
            self.adb = Adb(path, self.log)
            self.adb_label.configure(text=f"Using ADB: {path}")
            self.log(f"{APP_NAME} {VERSION} - using ADB at {path}")
            self.run_bg("Starting ADB", lambda: self.adb.run(["start-server"], device=False),
                        lambda r: self.refresh_devices())
        else:
            self.adb_label.configure(text="ADB not found. Click 'Download ADB from Google' (about 7 MB).")
            self.status.configure(text=self._status_text())

    def on_download_adb(self):
        def job():
            return download_adb(self.log)

        def done(path):
            if path:
                self.init_adb()
            else:
                messagebox.showerror(APP_NAME, "Download failed. Install 'Android SDK Platform Tools' manually "
                                               "(Windows: winget install Google.PlatformTools, macOS: brew install "
                                               "android-platform-tools, Linux: sudo apt install adb) and restart.")
        self.run_bg("Downloading ADB", job, done)

    def refresh_devices(self):
        if not self.adb:
            return
        def done(devs):
            self.devices = devs or []
            labels = []
            for serial, st, model in self.devices:
                hint = {"unauthorized": "  - tap 'Allow' on the phone, then Refresh",
                        "offline": "  - reconnect the cable"}.get(st, "")
                labels.append(f"{model or 'Android device'}  ({serial})  [{st}]{hint}")
            self.dev_combo["values"] = labels
            if not self.devices:
                self.dev_combo.set("")
                self.dev_label.configure(text="No phone found. Check the cable and that USB debugging is on.")
                self.adb.serial = None
                self.status.configure(text=self._status_text())
                return
            ready = [i for i, d in enumerate(self.devices) if d[1] == "device"]
            idx = ready[0] if ready else 0
            self.dev_combo.current(idx)
            self.select_device()
        self.run_bg("Looking for phones", self.adb.devices, done)

    def select_device(self):
        idx = self.dev_combo.current()
        if idx < 0 or idx >= len(self.devices):
            return
        serial, st, _ = self.devices[idx]
        if st != "device":
            self.adb.serial = None
            self.dev_label.configure(text=f"Phone is '{st}'. Unlock it, accept the debugging prompt, then Refresh.")
            self.status.configure(text=self._status_text())
            return
        self.adb.serial = serial

        def job():
            info = self.adb.info()
            state = self.adb.package_state()
            return info, state

        def done(res):
            if not res:
                return
            self.info, self.state = res
            self.backup = Backup(serial)
            i = self.info
            self.dev_label.configure(text=(
                f"{i['manufacturer'].title()} {i['model']}  |  Android {i['android']} (API {i['sdk']})  |  "
                f"{len(self.state['installed'])} packages, {len(self.state['user'])} installed by you"))
            self.log(f"Connected to {i['manufacturer']} {i['model']} (Android {i['android']})")
            self.status.configure(text=self._status_text())
            vendor = self._vendor_group()
            self.filter_combo.set("Suggested for this phone")
            if vendor:
                self.log(f"Detected {vendor} - showing Google + {vendor} + 3rd-party lists.")
            self.fill_debloat()
            self.fill_restore()
            self.fill_apps()
        self.run_bg("Reading phone", job, done)

    def on_dry(self):
        if self.adb:
            self.adb.dry_run = self.dry_var.get()
            self.log("Dry run ON - commands will be printed, not executed." if self.adb.dry_run else "Dry run OFF.")
            self.status.configure(text=self._status_text())

    def on_pair(self):
        addr, code = self.pair_addr.get().strip(), self.pair_code.get().strip()
        if not self.adb or not re.match(r"^[\w.\-:\[\]]+$", addr) or not code.isdigit():
            messagebox.showwarning(APP_NAME, "Enter the pairing IP:port and the 6-digit code from the phone.")
            return
        self.run_bg("Pairing", lambda: self.adb.run(["pair", addr, code], device=False),
                    lambda r: self.log(r[1] if r else "pair failed"))

    def on_connect(self):
        addr = self.conn_addr.get().strip()
        if not self.adb or not re.match(r"^[\w.\-:\[\]]+$", addr):
            messagebox.showwarning(APP_NAME, "Enter the IP:port shown under Wireless debugging.")
            return
        def done(r):
            self.log(r[1] if r else "connect failed")
            self.refresh_devices()
        self.run_bg("Connecting", lambda: self.adb.run(["connect", addr], device=False), done)

    # ----- tab 2: debloat -----
    def _tab_debloat(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  2. Debloat  ")
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Show:").pack(side="left")
        self.filter_combo = ttk.Combobox(top, state="readonly", width=34, values=(
            ["Suggested for this phone", "All lists"] + list(PACKAGES) + ["Every other installed app (expert)"]))
        self.filter_combo.set("Suggested for this phone")
        self.filter_combo.pack(side="left", padx=4)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self.fill_debloat())
        ttk.Label(top, text="  Search:").pack(side="left")
        self.search_var = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.search_var, width=24)
        e.pack(side="left", padx=4)
        self.search_var.trace_add("write", lambda *a: self.fill_debloat())
        self.only_installed = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Only apps on this phone", variable=self.only_installed,
                        command=self.fill_debloat).pack(side="left", padx=8)

        legend = ttk.Frame(f)
        legend.pack(fill="x", pady=(6, 4))
        for text, color in (("Recommended = bloat/telemetry, safe to remove", "#1b7f3b"),
                            ("Optional = real apps, your call", "#1f5fa8"),
                            ("Advanced = removes a system feature, read the note", "#b45f06")):
            tk.Label(legend, text="■ " + text, fg=color).pack(side="left", padx=(0, 16))

        self.debloat = CheckTree(f, ("Package", "App", "List", "Rating", "On phone", "Note"),
                                 (240, 180, 185, 110, 75, 300), height=16)
        self.debloat.pack(fill="both", expand=True)

        bottom = ttk.Frame(f)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Select Recommended", command=self.select_recommended).pack(side="left")
        ttk.Button(bottom, text="Clear", command=lambda: self.debloat.set_all(lambda i: False)).pack(side="left", padx=4)
        self.method = tk.StringVar(value="uninstall")
        ttk.Label(bottom, text="     Method:").pack(side="left")
        ttk.Radiobutton(bottom, text="Uninstall for user (recommended)", value="uninstall",
                        variable=self.method).pack(side="left")
        ttk.Radiobutton(bottom, text="Disable", value="disable", variable=self.method).pack(side="left", padx=6)
        ttk.Button(bottom, text="Remove selected", style="Accent.TButton",
                   command=self.apply_debloat).pack(side="right")

    def _vendor_group(self):
        txt = (self.info.get("manufacturer", "") + " " + self.info.get("brand", "")).lower()
        for key, group in VENDOR_GROUPS.items():
            if key in txt:
                return group
        return None

    def _status_of(self, pkg):
        s = self.state
        if pkg in s["disabled"]:
            return "Disabled"
        if pkg in s["installed"]:
            return "Yes"
        if pkg in s["removed"]:
            return "Removed"
        return "-"

    def _debloat_rows(self):
        choice = self.filter_combo.get()
        if choice == "Every other installed app (expert)":
            known = {p[0] for rows in PACKAGES.values() for p in rows}
            return [(p, "", "Other", "unknown", "Not in DroidUtil's list - look it up before removing")
                    for p in sorted(self.state["installed"] - known) if not is_protected(p)]
        if choice == "Suggested for this phone":
            groups = ["Google", self._vendor_group(), "Pre-installed 3rd party & carrier"]
            if not self.adb or not self.adb.serial:
                groups = list(PACKAGES)
        elif choice == "All lists":
            groups = list(PACKAGES)
        else:
            groups = [choice]
        rows = []
        for g in groups:
            if g:
                rows += [(p, n, g, r, note) for p, n, r, note in PACKAGES[g]]
        return rows

    def fill_debloat(self):
        keep = set(self.debloat.checked)
        self.debloat.clear()
        q = self.search_var.get().lower().strip()
        connected = bool(self.adb and self.adb.serial)
        order = {"safe": 0, "optional": 1, "advanced": 2, "unknown": 3}
        for pkg, name, group, risk, note in sorted(self._debloat_rows(), key=lambda r: (order[r[3]], r[2], r[1])):
            st = self._status_of(pkg) if connected else "?"
            if connected and self.only_installed.get() and st not in ("Yes", "Disabled"):
                continue
            if q and q not in f"{pkg} {name} {note}".lower():
                continue
            removable = (st == "Yes") or not connected
            self.debloat.add(pkg, (pkg, name, group, RISK_LABEL[risk], st, note),
                             tag=risk if removable else "muted", checkable=removable)
            if pkg in keep and removable:
                self.debloat.toggle(pkg, True)

    def _risk_of(self, pkg):
        for rows in PACKAGES.values():
            for p, _, r, _ in rows:
                if p == pkg:
                    return r
        return "unknown"

    def select_recommended(self):
        self.debloat.set_all(lambda iid: self._risk_of(iid) == "safe")

    def apply_debloat(self):
        if not self.need_device():
            return
        sel = sorted(self.debloat.checked)
        if not sel:
            messagebox.showinfo(APP_NAME, "Tick some apps first (or click 'Select Recommended').")
            return
        risky = [p for p in sel if self._risk_of(p) in ("advanced", "unknown")]
        method = self.method.get()
        msg = (f"{'Uninstall' if method == 'uninstall' else 'Disable'} {len(sel)} app(s) for the main user?\n\n"
               "This is reversible from the Restore tab (and a factory reset brings everything back).")
        if risky:
            msg += (f"\n\n⚠ {len(risky)} of them are Advanced/Unknown and may break a feature:\n  "
                    + "\n  ".join(risky[:12]) + ("\n  ..." if len(risky) > 12 else ""))
        if not messagebox.askyesno(APP_NAME, msg, icon="warning" if risky else "question"):
            return

        def job():
            removed = disabled = fail = 0
            for pkg in sel:
                if is_protected(pkg):
                    self.log(f"Skipped protected package {pkg}")
                    continue
                if method == "uninstall":
                    action = self.adb.uninstall(pkg)
                else:
                    action = "disable" if self.adb.disable(pkg) else None
                if action == "uninstall":
                    removed += 1
                elif action == "disable":
                    disabled += 1
                else:
                    fail += 1
                if action and not self.adb.dry_run:
                    self.backup.add(action, pkg)
            parts = []
            if removed or method == "uninstall":
                parts.append(f"{removed} removed")
            if disabled or method == "disable":
                parts.append(f"{disabled} disabled" + (" (system apps Android won't uninstall)"
                                                        if method == "uninstall" and disabled else ""))
            self.log(f"Done: {', '.join(parts)}, {fail} failed.")
            return self.adb.package_state()

        def done(state):
            if state:
                self.state = state
            self.fill_debloat()
            self.fill_restore()
        self.run_bg("Removing apps", job, done)

    # ----- tab 3: privacy tweaks -----
    def _tab_tweaks(self):
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text="  3. Privacy tweaks  ")
        left = ttk.Frame(f)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(f)
        right.pack(side="right", fill="y", padx=(14, 0))

        box = ttk.LabelFrame(left, text="Private DNS (encrypts DNS & can block trackers system-wide)", padding=10)
        box.pack(fill="x")
        self.dns_combo = ttk.Combobox(box, state="readonly", width=40, values=[d[0] for d in DNS_PROVIDERS])
        self.dns_combo.current(1)
        self.dns_combo.pack(side="left")
        self.dns_custom = ttk.Entry(box, width=30)
        self.dns_custom.pack(side="left", padx=8)
        ttk.Label(box, text="(custom hostname)", foreground="#777").pack(side="left")

        box = ttk.LabelFrame(left, text="System settings", padding=10)
        box.pack(fill="both", expand=True, pady=8)
        self.tweak_vars = {}
        for tid, title, desc, _, default in TWEAKS:
            v = tk.BooleanVar(value=default)
            self.tweak_vars[tid] = v
            ttk.Checkbutton(box, text=title, variable=v).pack(anchor="w", pady=(6, 0))
            ttk.Label(box, text=desc, foreground="#555", wraplength=620, justify="left").pack(anchor="w", padx=24)

        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="Apply selected tweaks", style="Accent.TButton",
                   command=self.apply_tweaks).pack(side="left")
        ttk.Button(row, text="Undo all tweaks (restore original values)",
                   command=self.undo_tweaks).pack(side="left", padx=8)

        box = ttk.LabelFrame(right, text="Open on the phone", padding=10)
        box.pack(fill="x")
        ttk.Label(box, text="Things only you can change -\nthese open the right screen:",
                  foreground="#555", justify="left").pack(anchor="w", pady=(0, 6))
        for label, action in SETTINGS_SHORTCUTS:
            ttk.Button(box, text=label, width=28,
                       command=lambda a=action: self.need_device() and self.run_bg(
                           "Opening settings", lambda: self.adb.open_settings(a))).pack(pady=2)

        box = ttk.LabelFrame(right, text="When you're finished", padding=10)
        box.pack(fill="x", pady=10)
        ttk.Label(box, text="Leaving USB debugging on lets\nany computer you authorized\ncontrol the phone.",
                  foreground="#555", justify="left").pack(anchor="w")
        ttk.Button(box, text="Turn off USB debugging", width=28, command=self.disable_adb).pack(pady=(6, 0))

    def apply_tweaks(self):
        if not self.need_device():
            return
        changes = []
        name, host = DNS_PROVIDERS[self.dns_combo.current()]
        if host == "__custom__":
            host = self.dns_custom.get().strip()
            if not re.match(r"^[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$", host):
                messagebox.showwarning(APP_NAME, "Enter a valid DNS-over-TLS hostname, e.g. dns.example.com")
                return
        if host and self.info.get("sdk", 0) < 28:
            self.log("Private DNS needs Android 9+, skipping.")
        elif host == "__off__":
            changes.append(("global", "private_dns_mode", "off"))
        elif host == "__auto__":
            changes.append(("global", "private_dns_mode", "opportunistic"))
        elif host:
            changes += [("global", "private_dns_mode", "hostname"), ("global", "private_dns_specifier", host)]
        for tid, _, _, sets, _ in TWEAKS:
            if self.tweak_vars[tid].get():
                changes += sets
        self._apply_settings(changes, "Applying tweaks")

    def _apply_settings(self, changes, label):
        if not changes:
            messagebox.showinfo(APP_NAME, "Nothing selected.")
            return

        def job():
            ok = 0
            maxhz = None
            for ns, key, val in changes:
                if val == "__maxhz__":
                    if maxhz is None:
                        maxhz = self.adb.max_refresh_rate()
                        self.log(f"Highest refresh rate on this screen: {maxhz or 'unknown'} Hz")
                    if not maxhz:
                        continue
                    val = maxhz
                orig = self.adb.get_setting(ns, key)
                if not self.adb.dry_run:
                    self.backup.remember_setting(ns, key, orig)
                if self.adb.put_setting(ns, key, val):
                    ok += 1
                else:
                    self.log(f"  ! {ns}/{key} didn't stick (this phone may not support it)")
            self.log(f"Applied {ok}/{len(changes)} settings. Originals saved to {self.backup.path}")
        self.run_bg(label, job)

    # ----- tab: performance -----
    def _tab_performance(self):
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text="  4. Performance  ")
        left = ttk.Frame(f)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(f)
        right.pack(side="right", fill="y", padx=(14, 0))

        box = ttk.LabelFrame(left, text="Animation speed (biggest 'feels faster' win)", padding=10)
        box.pack(fill="x")
        self.anim_combo = ttk.Combobox(box, state="readonly", width=36, values=[a[0] for a in ANIM_CHOICES])
        self.anim_combo.current(1)
        self.anim_combo.pack(side="left")
        ttk.Label(box, text="  Same as Developer options > animation scales.", foreground="#555").pack(side="left")

        box = ttk.LabelFrame(left, text="System settings", padding=10)
        box.pack(fill="x", pady=8)
        self.perf_vars = {}
        for tid, title, desc, _, default in PERF_TWEAKS:
            v = tk.BooleanVar(value=default)
            self.perf_vars[tid] = v
            ttk.Checkbutton(box, text=title, variable=v).pack(anchor="w", pady=(6, 0))
            ttk.Label(box, text=desc, foreground="#555", wraplength=620, justify="left").pack(anchor="w", padx=24)

        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="Apply selected", style="Accent.TButton", command=self.apply_perf).pack(side="left")
        ttk.Button(row, text="Undo all tweaks (privacy + performance)", command=self.undo_tweaks).pack(side="left", padx=8)

        tips = ("Other speed-ups that live elsewhere in DroidUtil:\n"
                "  - Debloat tab: removing bloat frees RAM and stops background services.\n"
                "  - Samsung: 'Game Optimizing Service' (Advanced) throttles games - removing it\n"
                "    can raise game FPS but the phone may run hotter.\n"
                "  - Privacy tab: turning off Wi-Fi/Bluetooth scanning also saves battery.")
        ttk.Label(left, text=tips, foreground="#555", justify="left").pack(anchor="w", pady=(16, 0))

        box = ttk.LabelFrame(right, text="One-time actions", padding=10)
        box.pack(fill="x")
        for label, cmd, desc, timeout in PERF_ACTIONS:
            ttk.Button(box, text=label, width=32,
                       command=lambda l=label, c=cmd, t=timeout: self.perf_action(l, c, t)).pack(anchor="w", pady=(6, 0))
            ttk.Label(box, text=desc, foreground="#555", wraplength=300, justify="left").pack(anchor="w")

    def apply_perf(self):
        if not self.need_device():
            return
        changes = []
        val = ANIM_CHOICES[self.anim_combo.current()][1]
        if val is not None:
            changes += [("global", k, val) for k in ANIM_KEYS]
        sdk = self.info.get("sdk", 0)
        for tid, _, _, sets, _ in PERF_TWEAKS:
            if self.perf_vars[tid].get():
                if tid == "freezer" and sdk < 30:
                    self.log("App freezer needs Android 11+, skipping.")
                    continue
                changes += sets
        self._apply_settings(changes, "Applying performance tweaks")

    def perf_action(self, label, cmd, timeout):
        if not self.need_device():
            return
        if not messagebox.askyesno(APP_NAME, f"{label}?" + (
                "\n\nThis can take a long time - DroidUtil will look busy until it finishes."
                if timeout > 600 else "")):
            return

        def job():
            rc, out = self.adb.shell(cmd, change=True, timeout=timeout)
            self.log(f"{label}: " + ("finished." if rc == 0 else f"failed ({out or 'error'})"))
        self.run_bg(label, job)

    def undo_tweaks(self):
        if not self.need_device():
            return
        saved = dict(self.backup.data.get("settings", {}))
        if not saved:
            messagebox.showinfo(APP_NAME, "No saved originals for this phone - nothing to undo.")
            return
        if not messagebox.askyesno(APP_NAME, f"Restore {len(saved)} setting(s) to their original values?"):
            return

        def job():
            for k, orig in saved.items():
                ns, key = k.split("/", 1)
                self.adb.put_setting(ns, key, orig)
            if not self.adb.dry_run:
                self.backup.data["settings"] = {}
                self.backup.add("undo-tweaks", list(saved))
            self.log("Settings restored.")
        self.run_bg("Restoring settings", job)

    def disable_adb(self):
        if not self.need_device():
            return
        if messagebox.askyesno(APP_NAME, "Turn off USB debugging now? DroidUtil will disconnect from the phone.\n"
                                         "(Turn it back on in Developer options any time.)"):
            def job():
                self.adb.shell("settings put global adb_enabled 0", change=True)
            def done(_):
                if not self.adb.dry_run:
                    self.adb.serial = None
                    self.refresh_devices()
            self.run_bg("Turning off USB debugging", job, done)

    # ----- tab: install apps -----
    def _tab_install(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  5. Install apps  ")
        ttk.Label(f, text="Curated open-source privacy apps. Downloaded from F-Droid or the developer's official "
                          "site, then installed over ADB. Tip: install F-Droid or Obtainium too, so these keep updating.",
                  foreground="#555", wraplength=1050, justify="left").pack(anchor="w", pady=(0, 6))
        self.apps_tree = CheckTree(f, ("App", "Category", "What it does", "From", "On phone"),
                                   (170, 160, 470, 90, 80), height=17)
        self.apps_tree.pack(fill="both", expand=True)
        bottom = ttk.Frame(f)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Select starter pack", command=lambda: self.apps_tree.set_all(
            lambda i: self._app(i)[5] and self._app(i)[2] not in self.state["installed"])).pack(side="left")
        ttk.Button(bottom, text="Clear", command=lambda: self.apps_tree.set_all(lambda i: False)).pack(side="left", padx=4)
        ttk.Button(bottom, text="Install an APK file...", command=self.install_file).pack(side="left", padx=12)
        ttk.Button(bottom, text="Install selected", style="Accent.TButton", command=self.install_apps).pack(side="right")
        self.fill_apps()

    def _app(self, pkg):
        return next(a for a in APPS if a[2] == pkg)

    def fill_apps(self):
        keep = set(self.apps_tree.checked)
        self.apps_tree.clear()
        connected = bool(self.adb and self.adb.serial)
        for cat, name, pkg, source, desc, starter in APPS:
            on = ("Yes" if pkg in self.state["installed"] else "-") if connected else "?"
            src = {"fdroid": "F-Droid", "signal": "signal.org"}.get(source, "Official site")
            self.apps_tree.add(pkg, (("★ " if starter else "") + name, cat, desc, src, on),
                               tag="safe" if on == "Yes" else None)
            if pkg in keep:
                self.apps_tree.toggle(pkg, True)

    def install_apps(self):
        if not self.need_device():
            return
        sel = [a for a in APPS if a[2] in self.apps_tree.checked]
        if not sel:
            messagebox.showinfo(APP_NAME, "Tick some apps first (or click 'Select starter pack').")
            return
        if not messagebox.askyesno(APP_NAME, f"Download and install {len(sel)} app(s)?\n\n"
                                             + "\n".join(f"  - {a[1]}" for a in sel)):
            return

        def job():
            ok = []
            for cat, name, pkg, source, _, _ in sel:
                self.log(f"--- {name}")
                try:
                    cands = resolve_apk(pkg, source)
                except Exception as e:
                    self.log(f"  Couldn't look up {name}: {e}")
                    continue
                for n, (url, sha) in enumerate(cands):
                    if self.adb.dry_run:
                        self.log(f"  [dry run] would download {url}")
                        ok.append(name)
                        break
                    try:
                        self.log(f"  Downloading {url}")
                        path = download_apk(url, sha)
                    except Exception as e:
                        self.log(f"  Download failed: {e}")
                        break
                    good, out = self.adb.install_apk(path)
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    if good:
                        ok.append(name)
                        self.backup.add("install", pkg)
                        break
                    if "NO_MATCHING_ABIS" in out and n + 1 < len(cands):
                        self.log("  Wrong CPU type for this phone - trying the next build...")
                        continue
                    if "UPDATE_INCOMPATIBLE" in out:
                        self.log(f"  {name} is already installed from another source (e.g. Play Store) with a "
                                 "different signature. Uninstall it on the phone first, then retry.")
                    elif "OLDER_SDK" in out or "DEPRECATED_SDK" in out:
                        self.log(f"  {name} doesn't support this Android version.")
                    break
            self.log(f"Installed {len(ok)}/{len(sel)}: {', '.join(ok) or 'none'}")
            return self.adb.package_state()

        def done(state):
            if state:
                self.state = state
            self.apps_tree.set_all(lambda i: False)
            self.fill_apps()
        self.run_bg("Installing apps", job, done)

    def install_file(self):
        if not self.need_device():
            return
        path = filedialog.askopenfilename(title="Choose an APK", filetypes=[("Android apps", "*.apk")])
        if not path:
            return

        def job():
            self.adb.install_apk(path)
            return self.adb.package_state()

        def done(state):
            if state:
                self.state = state
            self.fill_apps()
        self.run_bg("Installing APK", job, done)

    # ----- tab: permissions -----
    def _tab_permissions(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  6. App permissions  ")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        ttk.Button(top, text="Scan my apps", style="Accent.TButton", command=self.scan_perms).pack(side="left")
        ttk.Label(top, text="   Lists apps you installed that currently hold sensitive permissions. "
                            "Tick and revoke anything that doesn't need it - the app will just ask again.",
                  foreground="#555").pack(side="left")
        self.perms = CheckTree(f, ("App package", "Permission", "Android name"), (300, 200, 380), height=18)
        self.perms.pack(fill="both", expand=True)
        bottom = ttk.Frame(f)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Select all location/mic/camera", command=lambda: self.perms.set_all(
            lambda i: any(k in i for k in ("LOCATION", "RECORD_AUDIO", "CAMERA")))).pack(side="left")
        ttk.Button(bottom, text="Clear", command=lambda: self.perms.set_all(lambda i: False)).pack(side="left", padx=4)
        ttk.Button(bottom, text="Revoke selected", style="Accent.TButton", command=self.revoke_perms).pack(side="right")

    def scan_perms(self):
        if not self.need_device():
            return

        def job():
            apps = sorted(self.adb.packages("-3"))
            self.log(f"Scanning {len(apps)} apps...")
            res = []
            for n, pkg in enumerate(apps, 1):
                for perm in self.adb.granted_sensitive(pkg):
                    res.append((pkg, perm))
                if n % 20 == 0:
                    self.log(f"  {n}/{len(apps)}")
            return res

        def done(res):
            self.perms.clear()
            for pkg, perm in res or []:
                self.perms.add(f"{pkg}|{perm}", (pkg, SENSITIVE_PERMS[perm], perm),
                               tag="advanced" if "BACKGROUND" in perm else None)
            self.log(f"Found {len(res or [])} sensitive grants.")
        self.run_bg("Scanning permissions", job, done)

    def revoke_perms(self):
        if not self.need_device():
            return
        sel = [i.split("|") for i in self.perms.checked]
        if not sel or not messagebox.askyesno(APP_NAME, f"Revoke {len(sel)} permission(s)?"):
            return

        def job():
            done_ids = []
            for pkg, perm in sel:
                if self.adb.revoke(pkg, perm):
                    done_ids.append(f"{pkg}|{perm}")
                    if not self.adb.dry_run:
                        self.backup.add("revoke", f"{pkg} {perm}")
            self.log(f"Revoked {len(done_ids)}/{len(sel)}.")
            return done_ids

        def done(ids):
            if not self.adb.dry_run:
                for i in ids or []:
                    if self.perms.tree.exists(i):
                        self.perms.tree.delete(i)
                        self.perms.checked.discard(i)
        self.run_bg("Revoking", job, done)

    # ----- tab 5: restore -----
    def _tab_restore(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  7. Restore  ")
        ttk.Label(f, text="System apps that are currently removed or disabled on this phone. "
                          "Tick any you want back.", foreground="#555").pack(anchor="w", pady=(0, 6))
        self.restore = CheckTree(f, ("Package", "App", "State"), (330, 260, 120), height=18)
        self.restore.pack(fill="both", expand=True)
        bottom = ttk.Frame(f)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Refresh", command=self.refresh_restore).pack(side="left")
        ttk.Button(bottom, text="Select all", command=lambda: self.restore.set_all(lambda i: True)).pack(side="left", padx=4)
        ttk.Button(bottom, text="Restore selected", style="Accent.TButton", command=self.apply_restore).pack(side="right")

    def fill_restore(self):
        self.restore.clear()
        names = {p: n for rows in PACKAGES.values() for p, n, _, _ in rows}
        for pkg in sorted(self.state["removed"]):
            self.restore.add(pkg, (pkg, names.get(pkg, ""), "Removed"))
        for pkg in sorted(self.state["disabled"]):
            self.restore.add(pkg, (pkg, names.get(pkg, ""), "Disabled"))

    def refresh_restore(self):
        if not self.need_device():
            return
        def done(state):
            if state:
                self.state = state
                self.fill_restore()
        self.run_bg("Reading packages", self.adb.package_state, done)

    def apply_restore(self):
        if not self.need_device():
            return
        sel = sorted(self.restore.checked)
        if not sel:
            return
        removed, disabled = self.state["removed"], self.state["disabled"]

        def job():
            ok = 0
            for pkg in sel:
                good = True
                if pkg in removed:
                    good = self.adb.restore(pkg)
                if pkg in disabled or (pkg in removed and pkg in disabled):
                    good = self.adb.enable(pkg) and good
                ok += good
                if good and not self.adb.dry_run:
                    self.backup.add("restore", pkg)
            self.log(f"Restored {ok}/{len(sel)}.")
            return self.adb.package_state()

        def done(state):
            if state:
                self.state = state
            self.fill_restore()
            self.fill_debloat()
        self.run_bg("Restoring apps", job, done)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
