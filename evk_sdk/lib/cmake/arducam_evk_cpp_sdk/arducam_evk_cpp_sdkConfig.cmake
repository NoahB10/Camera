
####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was arducam_evk_cpp_sdkConfig.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../" ABSOLUTE)

macro(set_and_check _var _file)
  set(${_var} "${_file}")
  if(NOT EXISTS "${_file}")
    message(FATAL_ERROR "File or directory ${_file} referenced by variable ${_var} does not exist !")
  endif()
endmacro()

macro(check_required_components _NAME)
  foreach(comp ${${_NAME}_FIND_COMPONENTS})
    if(NOT ${_NAME}_${comp}_FOUND)
      if(${_NAME}_FIND_REQUIRED_${comp})
        set(${_NAME}_FOUND FALSE)
      endif()
    endif()
  endforeach()
endmacro()

####################################################################################

include("${CMAKE_CURRENT_LIST_DIR}/arducam_evk_cpp_sdkTargets.cmake")

# option(WITH_STD_OPTIONAL "Use std::optional" OFF)
# option(WITH_STD_STRING_VIEW "Use std::string_view" OFF)
# if(WITH_STD_OPTIONAL)
#     set(MACRO_DEFS ${MACRO_DEFS} WITH_STD_OPTIONAL=1)
# endif()
# if(WITH_STD_STRING_VIEW)
#     set(MACRO_DEFS ${MACRO_DEFS} WITH_STD_STRING_VIEW=1)
# endif()
# set(arducam_evk_cpp_sdk_MACRO_DEFS ${MACRO_DEFS})
# unset(MACRO_DEFS)
message(STATUS "arducam_evk_cpp_sdk Cmake Usage:")
# message(STATUS "  target_include_directories(\${APP_NAME} PUBLIC \${arducam_evk_cpp_sdk_INCLUDE_DIR})")
# message(STATUS "  target_compile_definitions(\${APP_NAME} PUBLIC \${arducam_evk_cpp_sdk_MACRO_DEFS})")
message(STATUS "  target_link_libraries(\${APP_NAME} PUBLIC arducam_evk_cpp_sdk)")

get_filename_component(arducam_evk_cpp_sdk_INCLUDE_DIR
  ${CMAKE_CURRENT_LIST_DIR}/../../../include
  ABSOLUTE
)
get_filename_component(arducam_evk_cpp_sdk_LIB_DIR
  ${CMAKE_CURRENT_LIST_DIR}/../..
  ABSOLUTE
)

# set(arducam_evk_cpp_sdk_STATIC_LIBS
#   ${arducam_evk_cpp_sdk_LIB_DIR}/libarducam_evk_cpp_sdk_static.a
# )
