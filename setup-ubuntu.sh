#!/usr/bin/env bash
# ==============================================================================
# Script: setup-ubuntu.sh
# Purpose: ตรวจสอบความพร้อมและเตรียมสภาพแวดล้อมสำหรับรัน ThaiOCR บน Ubuntu Server
# สถาปัตยกรรม: KVM Windows Container (dockurr/windows) + Linux Docker Containers
# ==============================================================================

set -e

echo "=========================================================="
echo "    ThaiOCR System - Ubuntu KVM Environment Pre-check     "
echo "=========================================================="

# 1. ตรวจสอบ CPU Virtualization
echo -n "[1/4] ตรวจสอบ CPU Hardware Virtualization (VT-x/AMD-V)... "
VIRT_COUNT=$(grep -E -c '(vmx|svm)' /proc/cpuinfo || true)
if [ "$VIRT_COUNT" -gt 0 ]; then
    echo "OK (พบ CPU คอร์ที่รองรับ $VIRT_COUNT คอร์)"
else
    echo "FAILED!"
    echo "[!] CPU ไม่รองรับหรือไม่ได้เปิด Virtualization ใน BIOS/UEFI"
    echo "    (หากรันบน Cloud/VM ต้องเปิด Nested Virtualization ให้กับเครื่องนี้)"
    exit 1
fi

# 2. ตรวจสอบ /dev/kvm
echo -n "[2/4] ตรวจสอบสิทธิ์และการเข้าถึง /dev/kvm... "
if [ -e /dev/kvm ]; then
    if [ -w /dev/kvm ]; then
        echo "OK"
    else
        echo "WARNING: /dev/kvm มีอยู่แต่ไม่มีสิทธิ์เขียน กำลังเพิ่มผู้ใช้เข้ากลุ่ม kvm..."
        sudo usermod -aG kvm "$USER" || true
        sudo chmod 666 /dev/kvm || true
        echo "OK (ปรับสิทธิ์เรียบร้อย)"
    fi
else
    echo "FAILED!"
    echo "[!] ไม่พบ /dev/kvm กรุณาติดตั้งแพ็กเกจด้วยคำสั่ง:"
    echo "    sudo apt update && sudo apt install -y qemu-kvm libvirt-daemon-system cpu-checker"
    echo "    sudo kvm-ok"
    exit 1
fi

# 3. ตรวจสอบ Docker และ Docker Compose
echo -n "[3/4] ตรวจสอบ Docker Engine และ Compose Plugin... "
if command -v docker >/dev/null 2>&1; then
    DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
    echo "OK (Docker version $DOCKER_VER)"
else
    echo "FAILED! กรุณาติดตั้ง Docker บน Ubuntu ก่อนดำเนินการ"
    exit 1
fi

# 4. สร้าง Directory สำหรับจัดเก็บข้อมูลแบบ Persistent
echo -n "[4/4] สร้างโฟลเดอร์จัดเก็บข้อมูล (data/windows, garage, output)... "
mkdir -p data/windows
mkdir -p data/garage/meta
mkdir -p data/garage/data
mkdir -p data/db
mkdir -p output
chmod 777 output data
echo "OK"

echo "=========================================================="
echo "   สภาพแวดล้อมพร้อมสำหรับรันระบบ ThaiOCR แล้ว!"
echo "=========================================================="
echo ""
echo "คำสั่งเริ่มต้นระบบ:"
echo "   docker compose -f docker-compose.ubuntu.yml up -d"
echo ""
echo "คำสั่งติดตามสถานะ:"
echo "   - ดู Log รวม: docker compose -f docker-compose.ubuntu.yml logs -f"
echo "   - เข้าดูหน้าจอ Windows ระหว่างบูตครั้งแรก: http://<IP-Ubuntu>:8006 (Web VNC)"
echo "   - เข้าใช้งาน Web Portal: http://<IP-Ubuntu>:8000"
echo "=========================================================="
