#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "arducam_evk_cpp_sdk" for configuration "Release"
set_property(TARGET arducam_evk_cpp_sdk APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(arducam_evk_cpp_sdk PROPERTIES
  IMPORTED_IMPLIB_RELEASE "${_IMPORT_PREFIX}/lib/arducam_evk_cpp_sdk.lib"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/arducam_evk_cpp_sdk.dll"
  )

list(APPEND _IMPORT_CHECK_TARGETS arducam_evk_cpp_sdk )
list(APPEND _IMPORT_CHECK_FILES_FOR_arducam_evk_cpp_sdk "${_IMPORT_PREFIX}/lib/arducam_evk_cpp_sdk.lib" "${_IMPORT_PREFIX}/bin/arducam_evk_cpp_sdk.dll" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
