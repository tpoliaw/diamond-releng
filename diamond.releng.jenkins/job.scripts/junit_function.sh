# run JUnit tests in a Jenkins "Execute shell" build step

#------------------------------------#
#------------------------------------#

junit_function () {

    # Save xtrace state (1=was not set, 0=was set)
    if [[ $- = *x* ]]; then
        oldxtrace=0
    else
        oldxtrace=1
    fi
    set +x  # Turn off xtrace

    # Save errexit state (1=was not set, 0=was set)
    if [[ $- = *e* ]]; then
        olderrexit=0
    else
        olderrexit=1
    fi
    set -e  # Turn on errexit

    ###
    ### Setup environment
    ###

    run_junit_tests=$(echo ${run_junit_tests:-true} | tr '[:upper:]' '[:lower:]')
    halt_on_failed_junit_tests=$(echo ${halt_on_failed_junit_tests:-false} | tr '[:upper:]' '[:lower:]')

    # GDALargeTestFilesLocation specifies the (optional) directory holding large test files that are not held in any repository
    # It's not set in any properties file, since the location can be different on each Jenkins slave
    # Instead, it's set in the slave "Node Properties" (exposed as an environment variable), though not on all nodes
    if [[ "${GDALargeTestFilesLocation}" == "none" || -z "${GDALargeTestFilesLocation-arbitrary}" ]]; then
        # explicitly pass an empty GDALargeTestFilesLocation if the environment variable is "none", or set but null 
        GDALargeTestFilesLocation_param=--GDALargeTestFilesLocation=
    elif [[ -n "${GDALargeTestFilesLocation}" ]]; then
        GDALargeTestFilesLocation_param=--GDALargeTestFilesLocation=${GDALargeTestFilesLocation}
    else
        # don't pass GDALargeTestFilesLocation to pewma.py, so it will look for it in a standard location
        GDALargeTestFilesLocation_param=
    fi
    echo "set ${GDALargeTestFilesLocation_param}"

    ###
    ### Run Junit tests
    ###

    if [[ -n "${nice_setting_common:-}" ]]; then
        python="nice -n ${nice_setting_common} python"
    else
        python="python"
    fi

    set -x  # Turn on xtrace

    echo -e "\n  *** `date +"%a %d/%b/%Y %H:%M:%S %z"` Running JUnit tests ***\n  "

    # Create a file whose content signals Jenkins that this build is to be marked UNSTABLE.
    # After the tests are run, clear the content if no problems are found.
    # If major errors (eg crash, timeout) occur during the build / tests, the file content is left there for the Jenkins Text-finder plugin.
    # This ensures that the build is, at best, UNSTABLE.
    #
    # Why do this? Jenkins (on Linux) will mark a build as SUCCESS if all the job steps have an exit code of zero, and if no tests report as failed in the JUnit test report XML.
    # The purpose of this process is to identify the case where a test fails in such a way that no JUnit test report XML is written, and the exit code is zero.
    # This scenario, though very unusual, can happen (and has occurred previously in testing), and results in the build being incorrectly marked as SUCCESS.
    #
    echo "$`date +"%a %d/%b/%Y %H:%M:%S %z"` (start of job) MARK_BUILD_AS_UNSTABLE (this text will be cleared if no problems found)" > ${WORKSPACE}/post_build_status_marker.txt

    # source the scripts that identify_changes_to_test_function.py possibly wrote
    #   gerrit_set.junit.options.sh  sets an environment variable of tests are to be skipped in the scanning repo

    for generated_script in gerrit_set.junit.options.sh; do
        if [ -f "${WORKSPACE}/artifacts_to_archive/${generated_script}" ]; then
            echo "Sourcing artifacts_to_archive/${generated_script}"
            . ${WORKSPACE}/artifacts_to_archive/${generated_script}
        fi
    done

    # Run JUnit tests
    ${pewma_py} -w ${materialize_workspace_path} ${junit_tests_skip_scanning:-} ${junit_tests_extra_parameters:-} ${junit_tests_system_properties:-} ${GDALargeTestFilesLocation_param:-} all-tests

    # If we get this far, clear the signal that tells Jenkins that this build is to be marked UNSTABLE
    echo "`date +"%a %d/%b/%Y %H:%M:%S %z"` (after build and tests) no need for Jenkins Text-finder plugin to override the build status" > ${WORKSPACE}/post_build_status_marker.txt

    # If any JVM abended, write text to console log (for reporting) and create the status file (so that Jenkins will mark the build as unstable)
    set +e  # Turn off errexit
    python ${WORKSPACE}/diamond-releng.git/diamond.releng.jenkins/job.scripts/check_if_JVM_abend.py ${materialize_workspace_path}_git
    RETVAL=$?
    if [ "${RETVAL}" != "0" ]; then
      echo -e "`date +"%a %d/%b/%Y %H:%M:%S %z"` (after build and tests) MARK_BUILD_AS_UNSTABLE (set by check_if_JVM_abend.py)" > ${WORKSPACE}/post_build_status_marker.txt
    fi

    $([ "$olderrexit" == "0" ]) && set -e || true  # Turn errexit on if it was on at the top of this script
    $([ "$olderrexit" == "1" ]) && set +e || true  # Turn errexit off if it was off at the top of this script
    $([ "$oldxtrace" == "0" ]) && set -x || true  # Turn xtrace on if it was on at the top of this script
    $([ "$oldxtrace" == "1" ]) && set +x || true  # Turn xtrace off if it was off at the top of this script

}

#------------------------------------#
#------------------------------------#

