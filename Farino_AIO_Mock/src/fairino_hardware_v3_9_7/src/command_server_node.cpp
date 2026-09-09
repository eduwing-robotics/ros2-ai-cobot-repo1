#include "fairino_hardware/command_server.hpp"
#include "rclcpp/rclcpp.hpp"
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include "fairino_hardware/CNDE_thread.hpp"

int main(int argc, char *argv[]){
    //该main函数用于创建简化指令客户端的app
    const char* domain = std::getenv("ROS_DOMAIN_ID");
    if (!domain || std::strcmp(domain, "5") != 0) {
        std::fprintf(stderr, "MODE_REJECTED stage=startup expected=real ROS_DOMAIN_ID=5 required; SDK not connected\n");
        return 1;
    }
    rclcpp::init(argc,argv);
    rclcpp::executors::MultiThreadedExecutor mulexecutor;

    //创建用户指令节点
    auto command_server_node = std::make_shared<robot_command_thread>("fr_command_server");
    mulexecutor.add_node(command_server_node);
    //创建非实时状态反馈获取节点
    auto CNDE_node = std::make_shared<CNDE_recv_thread>("CNDE_thread");
    mulexecutor.add_node(CNDE_node);//状态反馈节点加入执行器

    mulexecutor.spin();
    rclcpp::shutdown();

    return 0;
}
