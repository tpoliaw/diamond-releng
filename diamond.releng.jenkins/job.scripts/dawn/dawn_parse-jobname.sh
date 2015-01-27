# Parse the Jenkins jobname and extra certain information from it
# Write the information from the jobname into a temporary file in the form of name=value pairs
# The next step in the Jenkins job is "Inject Environment Variables" which sets the name=value pairs as environment variables for the remainder of the job
set +x  # Turn off xtrace

properties_filename=${WORKSPACE}/parsed-jobname.properties
rm -f ${properties_filename}

# The jobname must start with "DawnDiamond." or "DawnVanilla.", followed by the release, followed by "-", followed by anything

if [[ "${JOB_NAME:0:12}" == "DawnDiamond." || "${JOB_NAME:0:12}" == "DawnVanilla." ]]; then
    flavour=${JOB_NAME:4:7}
    releasesuffixindex=$(expr index "${JOB_NAME}" '-')
    if [[ "${releasesuffixindex}" != "0" ]]; then
        # -13 is -12 for "Dawn<flavour>." and -1 for "-"
        release=${JOB_NAME:12:${releasesuffixindex}-13}
        result=good
    fi

        if [[ "${release}" == "master" ]]; then
            repo_branch_name_for_release=master
        else
            repo_branch_name_for_release="dawn-${release}"
        fi

    if [[ "${JOB_NAME:-noname}" == *download.public ]]; then
        download_public=true
    else
        download_public=false
    fi

    if [[ "${JOB_NAME:-noname}" =~ ^Dawn.+--publish-([a-z0-9]+)$ ]]; then
        publish_type=${BASH_REMATCH[1]}
    fi
    if [[ "${JOB_NAME:-noname}" =~ ^Dawn.+--publish-([a-z0-9]+)\.cleanup$ ]]; then
        cleanup_type=${BASH_REMATCH[1]}
    fi

fi

echo "Dawn_flavour=${flavour:Error}" >> ${properties_filename}
echo "Dawn_release=${release:Error}" >> ${properties_filename}
echo "repo_branch_name_for_release=${repo_branch_name_for_release:Error}" >> ${properties_filename}
echo "download_public=${download_public:Error}" >> ${properties_filename}
if [[ -n "${publish_type}" ]]; then
    echo "publish_type=${publish_type}" >> ${properties_filename}
fi
if [[ -n "${cleanup_type}" ]]; then
    echo "cleanup_type=${cleanup_type}" >> ${properties_filename}
fi
if [[ "${result:bad}" != "good" ]]; then
    echo "Error parsing \${JOB_NAME}=${JOB_NAME}"
    exit 2
fi

echo "[dawn_parse-jobname.sh] wrote ${properties_filename} --->"
cat ${properties_filename}

