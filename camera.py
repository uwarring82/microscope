"""Read-only discovery for the Di-Li / Tucsen legacy USB camera on macOS.

USB presence is deliberately separate from capture availability. No vendor USB
commands are sent without a documented protocol or a compatible vendor SDK.
"""

import platform
import re
import subprocess
from datetime import datetime, timezone

VENDOR_ID = 0x0547
PRODUCT_ID = 0xC004


def parse_registry(output):
    """Extract only this camera's information from ioreg's text tree."""
    nodes = re.split(r"(?=^[ |]*\+-o )", output, flags=re.MULTILINE)
    matches = []
    for index, node in enumerate(nodes):
        if "<class IOUSBHostDevice," not in node.split("\n", 1)[0]:
            continue

        def number(key):
            match = re.search(r'"' + re.escape(key) + r'" = (\d+)', node)
            return int(match[1]) if match else None

        def string(key):
            match = re.search(r'"' + re.escape(key) + r'" = "([^"\n]*)"', node)
            return match[1].strip() if match else None

        if (number("idVendor"), number("idProduct")) != (VENDOR_ID, PRODUCT_ID):
            continue
        interfaces = []
        for child in nodes[index + 1:]:
            heading = child.split("\n", 1)[0]
            if "<class IOUSBHostDevice," in heading:
                break
            if "<class IOUSBHostInterface," in heading:
                match = re.search(r'"bInterfaceClass" = (\d+)', child)
                if match:
                    interfaces.append(int(match[1]))
        matches.append({
            "name": string("USB Product Name") or "5MP-B CMOS Camera",
            "manufacturer": string("USB Vendor Name"),
            "serial": string("USB Serial Number"),
            "vendor_id": f"{VENDOR_ID:04x}",
            "product_id": f"{PRODUCT_ID:04x}",
            "link_mbps": number("UsbLinkSpeed") / 1_000_000 if number("UsbLinkSpeed") else None,
            "interface_classes": interfaces,
        })
    return matches


def status():
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "usb_state": "unknown",
        "devices": [],
        "capture_available": False,
        "capture_state": "driver_required",
        "message": "A compatible camera SDK is needed for live view and hardware controls.",
    }
    if platform.system() != "Darwin":
        result["message"] = "USB discovery currently supports macOS. Camera capture is not implemented."
        return result
    try:
        completed = subprocess.run(
            ["/usr/sbin/ioreg", "-p", "IOService", "-r", "-c", "IOUSBHostDevice", "-l", "-w", "0"],
            capture_output=True, text=True, timeout=8, check=True,
        )
        if completed.stderr.strip():
            raise RuntimeError(completed.stderr.strip())
        result["devices"] = parse_registry(completed.stdout)
        result["usb_state"] = "connected" if result["devices"] else "disconnected"
        if not result["devices"]:
            result["message"] = "The 0547:c004 camera was not found. Check its USB cable and power."
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        result["message"] = f"USB discovery failed: {error}"
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(status(), indent=2))

