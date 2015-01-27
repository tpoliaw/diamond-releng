# Parse the Jenkins jobname and extra certain information from it
# Write the information from the jobname into a temporary file in the form of name=value pairs
# The next step in the Jenkins job is "Inject Environment Variables" which sets the name=value pairs as environment variables for the remainder of the job
set +x  # Turn off xtrace

properties_filename=${WORKSPACE}/parsed-jobname.properties
rm -f ${properties_filename}

# The jobname must start with "GDA.", followed by the release (e.g. master, 8.42), followed by a dash (-)
# IF the jobname contains ".beamline-GROUP-", it must be followed by <beamline name> (which may contain a -), optionally followed by -download.public
# OTHERWISE group and beamline do not apply

if [[ "${JOB_NAME:0:4}" == "GDA." ]]; then
    releasesuffixindex=$(expr index "${JOB_NAME}" '-')
    if [[ "${releasesuffixindex}" != "0" ]]; then
        # -5 is -4 for "GDA." and -1 for "-"
        release=${JOB_NAME:4:${releasesuffixindex}-5}

        if [[ "${release}" == "master" ]]; then
            repo_branch_name_for_release=master
        else
            repo_branch_name_for_release="gda-${release}"
        fi

        groupbeamlinesuffixindex=$(expr match "${JOB_NAME:-noname}" 'GDA\..*beamline-')
        if [[ "${groupbeamlinesuffixindex}" != "0" ]]; then
            groupbeamlinesuffix=${JOB_NAME:groupbeamlinesuffixindex}
            dash=$(expr index ${groupbeamlinesuffix} '-') || true
            if [[ "${dash}" != "0" ]]; then
                group=${groupbeamlinesuffix:0:${dash}-1}
                beamlinesuffix=${groupbeamlinesuffix:${dash}}
                beamline=${beamlinesuffix%%-download.public}
                if [[ "${JOB_NAME:-noname}" == *create.product.beamline* ]]; then
                    squish_job_to_trigger=$(echo "${JOB_NAME}" | sed 's/create.product.beamline/squish.beamline/')
                fi
                if [[ "${JOB_NAME:-noname}" == *squish.beamline* ]]; then
                    product_job_to_test=$(echo "${JOB_NAME}" | sed 's/squish.beamline/create.product.beamline/')
                fi
                result=good
            fi
        else
            # group and beamline do not apply, only release
            result=good
        fi
    fi

    if [[ "${JOB_NAME:-noname}" == *download.public ]]; then
        download_public=true
    else
        download_public=false
    fi
    if [[ "${JOB_NAME:-noname}" == *new.config* ]]; then
        new_config_test=true
    else
        new_config_test=false
    fi
    if [[ "${JOB_NAME:-noname}" == *gerrit* ]]; then
        gerrit_test=true
    else
        gerrit_test=false
    fi

fi

echo "GDA_release=${release:Error}" >> ${properties_filename}
echo "repo_branch_name_for_release=${repo_branch_name_for_release:Error}" >> ${properties_filename}

if [[ -n "${group}" ]]; then
    echo "GDA_group=${group}" >> ${properties_filename}
fi
if [[ -n "${beamline}" ]]; then
    echo "GDA_beamline=${beamline}" >> ${properties_filename}
fi
if [[ -n "${squish_job_to_trigger}" ]]; then
    echo "GDA_squish_job_to_trigger=${squish_job_to_trigger}" >> ${properties_filename}
fi
if [[ -n "${product_job_to_test}" ]]; then
    echo "GDA_product_job_to_test=${product_job_to_test}" >> ${properties_filename}
fi
echo "download_public=${download_public:Error}" >> ${properties_filename}
echo "new_config_test=${new_config_test:Error}" >> ${properties_filename}
echo "gerrit_test=${gerrit_test:Error}" >> ${properties_filename}

if [[ "${result:bad}" != "good" ]]; then
    echo "Error parsing \${JOB_NAME}=${JOB_NAME}"
    exit 2
fi

echo "[gda_parse-jobname.sh] wrote ${properties_filename} --->"
cat ${properties_filename}

