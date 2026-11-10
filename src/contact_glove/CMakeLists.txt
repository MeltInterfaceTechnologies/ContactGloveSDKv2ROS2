cmake_minimum_required(VERSION 3.8)
project(contact_glove)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake_auto REQUIRED)
ament_auto_find_build_dependencies()

find_package(ContactGloveSDKv2 1.0.0 CONFIG REQUIRED)
if(NOT TARGET ContactGloveSDKv2::ContactGloveSDKv2)
  message(FATAL_ERROR
    "ContactGloveSDKv2 package was found, but target "
    "ContactGloveSDKv2::ContactGloveSDKv2 is not available.")
endif()

ament_auto_add_library(contact_glove_conversions
  src/conversions.cpp
  src/rviz_conversions.cpp
)
target_link_libraries(contact_glove_conversions ContactGloveSDKv2::ContactGloveSDKv2)

ament_auto_add_executable(contact_glove_node src/contact_glove_node.cpp)
target_link_libraries(contact_glove_node contact_glove_conversions ContactGloveSDKv2::ContactGloveSDKv2)

ament_auto_add_executable(contact_glove_rviz_node src/contact_glove_rviz_node.cpp)
target_link_libraries(contact_glove_rviz_node contact_glove_conversions)

install(DIRECTORY launch config urdf
  DESTINATION share/${PROJECT_NAME}
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
  # We don't want to strictly enforce code *formatting*: uncrustify is
  # skipped entirely (AMENT_LINT_AUTO_EXCLUDE only suppresses the
  # ament_lint_auto-registered test; it does not prevent find_package() from
  # running, so ament_cpplint() below still gets defined), and cpplint's own
  # "whitespace/*" category (indentation, brace/paren placement, blank
  # lines, etc.) is relaxed via a manually re-added cpplint test with
  # FILTERS below. whitespace/empty_conditional_body, whitespace/empty_if_body
  # and whitespace/empty_loop_body are re-enabled within that category since
  # they catch a real bug (an accidental empty if/for/while body from a
  # stray semicolon), not a formatting preference. cpplint's other
  # categories (build/legal/readability/runtime, e.g. naming, includes,
  # correctness pitfalls) still run at full strictness.
  set(AMENT_LINT_AUTO_EXCLUDE ament_cmake_uncrustify ament_cmake_cpplint)
  ament_lint_auto_find_test_dependencies()
  ament_cpplint(FILTERS "-whitespace" "+whitespace/empty_conditional_body" "+whitespace/empty_if_body" "+whitespace/empty_loop_body")

  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(test_conversions test/test_conversions.cpp)
  target_link_libraries(test_conversions contact_glove_conversions)

  ament_add_gtest(test_rviz_conversions test/test_rviz_conversions.cpp)
  target_link_libraries(test_rviz_conversions contact_glove_conversions)

  ament_add_gtest(test_retarget_profile_request_tracker test/test_retarget_profile_request_tracker.cpp)
  target_link_libraries(
    test_retarget_profile_request_tracker
    contact_glove_conversions
    ContactGloveSDKv2::ContactGloveSDKv2)

  find_package(ament_cmake_test REQUIRED)
  # Exercise the native SDK library's public API, including the early-stop
  # regression. A hang must fail within a bounded time instead of stalling CI.
  add_executable(test_native_sdk_lifecycle test/test_native_sdk_lifecycle.cpp)
  target_link_libraries(test_native_sdk_lifecycle ContactGloveSDKv2::ContactGloveSDKv2)
  ament_add_test(test_native_sdk_lifecycle
    COMMAND "$<TARGET_FILE:test_native_sdk_lifecycle>"
    TIMEOUT 30
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO
  )

  # Verify that the revolute joint names in the left and right URDF files match
  # contact_glove::to_joint_state() output in JointState.name. xacro is an
  # exec_depend needed only at launch time and may not be installed in every
  # build environment, so omit these tests when it is unavailable rather than
  # blocking CI.
  find_program(XACRO_EXECUTABLE xacro)
  if(XACRO_EXECUTABLE)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    ament_add_test(check_urdf_joint_names_left
      COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/test/check_urdf_joint_names.py"
        --xacro "${XACRO_EXECUTABLE}"
        --urdf "${CMAKE_CURRENT_SOURCE_DIR}/urdf/left_hand.urdf.xacro"
        --side left
      GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    )
    ament_add_test(check_urdf_joint_names_right
      COMMAND "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_SOURCE_DIR}/test/check_urdf_joint_names.py"
        --xacro "${XACRO_EXECUTABLE}"
        --urdf "${CMAKE_CURRENT_SOURCE_DIR}/urdf/right_hand.urdf.xacro"
        --side right
      GENERATE_RESULT_FOR_RETURN_CODE_ZERO
    )
  else()
    message(STATUS "xacro executable not found; skipping check_urdf_joint_names tests.")
  endif()
endif()

ament_auto_package()
