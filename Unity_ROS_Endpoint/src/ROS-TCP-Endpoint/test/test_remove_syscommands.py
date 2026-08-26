from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call

from ros_tcp_endpoint.server import SysCommands


class TestRemoveSysCommands(unittest.TestCase):
    def test_remove_commands_are_idempotent(self):
        commands = {
            "remove_subscriber": "subscribers_table",
            "remove_publisher": "publishers_table",
            "remove_ros_service": "ros_services_table",
            "remove_unity_service": "unity_services_table",
        }

        for command_name, table_name in commands.items():
            with self.subTest(command=command_name):
                node = object()
                server = SimpleNamespace(
                    subscribers_table={},
                    publishers_table={},
                    ros_services_table={},
                    unity_services_table={},
                    unregister_node=Mock(),
                )
                table = getattr(server, table_name)
                table["/topic"] = node
                command = getattr(SysCommands(server), command_name)

                command("/topic")
                command("/topic")

                self.assertNotIn("/topic", table)
                self.assertEqual(server.unregister_node.call_args_list, [call(node), call(None)])


if __name__ == "__main__":
    unittest.main()
