#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "fairino_hardware_v3_9_7::fairino_hardware" for configuration "Release"
set_property(TARGET fairino_hardware_v3_9_7::fairino_hardware APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(fairino_hardware_v3_9_7::fairino_hardware PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/fairino_hardware_v3_9_7/libfairino_hardware.so"
  IMPORTED_SONAME_RELEASE "libfairino_hardware.so"
  )

list(APPEND _cmake_import_check_targets fairino_hardware_v3_9_7::fairino_hardware )
list(APPEND _cmake_import_check_files_for_fairino_hardware_v3_9_7::fairino_hardware "${_IMPORT_PREFIX}/lib/fairino_hardware_v3_9_7/libfairino_hardware.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
