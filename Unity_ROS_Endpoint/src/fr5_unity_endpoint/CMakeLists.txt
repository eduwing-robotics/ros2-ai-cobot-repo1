cmake_minimum_required(VERSION 3.8)
project(fr5_unity_endpoint)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})

ament_package()
