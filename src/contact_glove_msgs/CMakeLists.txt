cmake_minimum_required(VERSION 3.8)
project(contact_glove_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake_auto REQUIRED)
ament_auto_find_build_dependencies()

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/GloveData.msg"
  "msg/Ergonomics.msg"
  "msg/ThumbPose.msg"
  "msg/FingerPose.msg"
  "msg/Skeleton.msg"
  "msg/RawSkeleton.msg"
  "msg/RawSensorTransforms.msg"
  "msg/Controller.msg"
  "msg/HapticsBody.msg"
  "srv/GetRetargetProfile.srv"
  DEPENDENCIES
  geometry_msgs
  std_msgs
)

# Full guides and the hand-maintained API reference live on the documentation site.
# Install the same minimal bilingual entry points as the ZIP root.
install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/../../packaging/README.md
              ${CMAKE_CURRENT_SOURCE_DIR}/../../packaging/README_JA.md
  DESTINATION share/${PROJECT_NAME}
)

install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/../../LICENSE.md
              ${CMAKE_CURRENT_SOURCE_DIR}/../../NOTICE.md
              ${CMAKE_CURRENT_SOURCE_DIR}/../../THIRD_PARTY_NOTICES.md
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # Source files use short SPDX notices; ament_copyright requires full
  # boilerplate headers. Keep the existing header-style check disabled.
  # The Apache license and notices are installed for both packages.
  set(ament_cmake_copyright_FOUND TRUE)
  # See src/contact_glove/CMakeLists.txt for why uncrustify is skipped and
  # cpplint's formatting-only "whitespace/*" category is relaxed instead of
  # enforced. This package currently has no C++ sources for either linter to
  # check, but the exclude is kept in sync in case that changes.
  set(AMENT_LINT_AUTO_EXCLUDE ament_cmake_uncrustify ament_cmake_cpplint)
  ament_lint_auto_find_test_dependencies()
  # ament_cpplint() exits non-zero when it finds no files to check, so only
  # re-add it (mirroring the ament_cmake_cpplint_lint_hook.cmake source-file
  # guard) if this package ever gains C/C++ sources.
  file(GLOB_RECURSE _cpplint_source_files FOLLOW_SYMLINKS
    "*.c" "*.cc" "*.cpp" "*.cxx" "*.h" "*.hh" "*.hpp" "*.hxx"
  )
  if(_cpplint_source_files)
    ament_cpplint(FILTERS "-whitespace" "+whitespace/empty_conditional_body" "+whitespace/empty_if_body" "+whitespace/empty_loop_body")
  endif()
endif()

ament_auto_package()
