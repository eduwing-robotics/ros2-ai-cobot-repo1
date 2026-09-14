"""Offline duplicate-start guard contract; no ROS or hardware starts."""
from pathlib import Path
import xml.etree.ElementTree as ET


def test_overlay_launcher_guards_launcher_and_orphan_node():
    root = Path(__file__).resolve().parents[1]
    source = (root / "ros2_ws/run_conveyor_roi.sh").read_text()
    assert 'exec 9>"${KSMC_ROOT}/runtime/conveyor_roi.lock"' in source
    assert "flock -n 9" in source
    assert "'/lib/vision_server/conveyor_roi( |$)'" in source
    assert source.index("flock -n 9") < source.index("exec ros2 launch")


def test_laptop_transport_preserves_buffers_and_matches_interface_subnets():
    root = Path(__file__).resolve().parents[1]
    ns = {'d': 'http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles'}
    xml = ET.parse(root / 'config/fastdds_laptop.xml')
    udp = xml.find('.//d:transport_descriptor[d:type="UDPv4"]', ns)
    assert udp.find('d:sendBufferSize', ns).text == '4194304'
    assert udp.find('d:receiveBufferSize', ns).text == '4194304'
    assert udp.find('d:non_blocking_send', ns).text == 'true'
    assert udp.find('d:netmask_filter', ns).text == 'ON'
    entries = udp.findall('d:interfaces/d:allowlist/d:interface', ns)
    assert {e.get('name') for e in entries} == {'lo', 'wlo1', 'enp129s0'}
    assert all(e.get('netmask_filter') == 'ON' for e in entries)
    assert xml.find('.//d:segment_size', ns).text == '33554432'
    assert xml.find('.//d:maxMessageSize', ns) is None
