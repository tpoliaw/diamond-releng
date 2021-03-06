# clean up beamlines

#------------------------------------#
#------------------------------------#

# use the latest available version of xz
module load xz
echo "Compression will be done using xz from $(which xz)"
xz --version
xz --info-memory


archive_files () {
    # parent_dir        must be set and non-empty
    # archive_dir       must be set and non-empty
    if [[ -d "${parent_dir}" ]]; then
        echo -e "\n$(date '+%a %d/%b/%Y %H:%M:%S %z') Moving files older than 15 days from ${parent_dir} to ${archive_dir} ..."

        find_command="${parent_dir} -mindepth 1 -maxdepth 1 -type f ""( -name ""*.gz"" -o -name ""*.xz"" -o -name ""*.zip"" "") -mtime +15"
        count=$(find ${find_command} | wc -l)
        echo "${count} items found by: find ${find_command}"
        if [[ "${count}" != "0" ]]; then
            if [[ "${dryrun}" != "false" ]]; then
                find ${find_command} -print | sort
                echo "If not in dryrun mode, would run: find ${find_command} -exec rsync -a --no-owner --remove-source-files --out-format=\"%-50n %B %12l %M\" {} ${archive_dir} \; || true"
            else
                mkdir_command="mkdir -pv ${archive_dir}"
                echo "Running: ${mkdir_command}"
                ${mkdir_command}
                echo "Running: find ${find_command} -exec rsync -a --no-owner --remove-source-files --out-format=\"%-50n %B %12l %M\" {} ${archive_dir} \; || true"
                find ${find_command} -exec rsync -a --no-owner --remove-source-files --out-format="%-50n %B %12l %M" {} ${archive_dir} \; || true
            fi
        fi
    fi
}


compress_files () {
    # parent_dir        must be set and non-empty
    # filename_pattern  must be set and non-empty
    if [[ -d "${parent_dir}" ]]; then
        echo -e "\n$(date '+%a %d/%b/%Y %H:%M:%S %z') Compressing files older than 7 days in ${parent_dir}, matching ${filename_pattern} ..."

        find_command="${parent_dir} -mindepth 1 -maxdepth 1 -type f -name ${filename_pattern} -mtime +7"
        count=$(find ${find_command} | wc -l)
        echo "${count} items found by: find ${find_command}"
        if [[ "${count}" != "0" ]]; then
            if [[ "${dryrun}" != "false" ]]; then
                find ${find_command} -print | sort
                echo "If not in dryrun mode, would run: find ${find_command} -exec xz -z {} \; || true"
            else
                echo "Running: find ${find_command} -exec xz -z {} \; || true"
                echo "Note: if you see this, it is only a warning, the compression has still been done: 'Cannot set the file group: Operation not permitted'"
                find ${find_command} -exec xz -z {} \; || true
            fi
        fi
    fi
}

#------------------------------------#

archive_beamline () {

    if [[ -z "${beamline}" ]]; then
        echo '$beamline variable was not set - exiting'
        return 1
    fi
    echo -e "\n********************************************************************************"
    echo -e "*** `date +"%a %d/%b/%Y %H:%M:%S %z"` Processing beamline ${beamline} ***"
    echo -e "********************************************************************************"
    if [[ "${dryrun}" != "false" ]]; then
        echo 'Running in dryrun mode ($dryrun != false)'
    fi

    # Compress old logs (GDA 8 log locations)
    parent_dir="/dls_sw/${beamline}/logs"
    filename_pattern='*.txt'
    compress_files

    # Compress old logs (GDA 9 log locations - pre Aug/2017 naming, using underscores)
    for type in client servers logpanel; do
        parent_dir="/dls_sw/${beamline}/logs/gda_${type}_output"
        filename_pattern='*.txt'
        compress_files
    done
    # Compress old logs (GDA 9 log locations - post Aug/2017 naming, using hyphens)
    for type in client servers logpanel; do
        parent_dir="/dls_sw/${beamline}/logs/gda-${type}-output"
        filename_pattern='*.txt'
        compress_files
    done

    # Compress old terminal logs
    parent_dir="/dls_sw/${beamline}/logs/terminal_output"
    filename_pattern='*.txt'
    compress_files

    # Move old logs to archive (GDA 8 log locations)
    parent_dir="/dls_sw/${beamline}/logs"
    archive_dir=/dls/science/groups/das/Archive/${beamline}/logs
    archive_files

    # Move old logs to archive (GDA 9 log locations - pre Aug/2017 naming, using underscores)
    for type in client servers logpanel; do
        parent_dir="/dls_sw/${beamline}/logs/gda_${type}_output"
        archive_dir="/dls/science/groups/das/Archive/${beamline}/logs/gda_${type}_output"
        archive_files
    done
    # Move old logs to archive (GDA 9 log locations - post Aug/2017 naming, using hyphens)
    for type in client servers logpanel; do
        parent_dir="/dls_sw/${beamline}/logs/gda-${type}-output"
        archive_dir="/dls/science/groups/das/Archive/${beamline}/logs/gda-${type}-output"
        archive_files
    done

    # Move old terminal logs to archive
    parent_dir="/dls_sw/${beamline}/logs/terminal_output"
    archive_dir=/dls/science/groups/das/Archive/${beamline}/logs/terminal_output
    archive_files

    # After some discussion with Mark Booth, we decide to skip the cleanup of the var/ directory for the moment
    # As lots of things can go in there, it's possible that old files are simply ones that are static, and are still required
    echo -e "\nCleanup of var/ is currently skipped for all beamlines"
    echo -e "-- end of ${beamline} cleanup\n"
    return

    # From Charles:
    #   Can the removal of old files from var please _not_ be run against B16, I07, I16.
    #   They have some old persistence stuff there (which, despite having mtime dates going back over a year, I think might still be used).
    if [[ "${beamline}" == "b16" || "${beamline}" == "i07" || "${beamline}" == "i16" ]]; then
        echo -e "\nCleanup of var/ is always skipped for this beamline ${beamline}"
        return
    fi

    # Delete old files from var/ (excluding some sub-directories, which might be in active use)
    parent_dir="/dls_sw/${beamline}/var"
    if [[ -d "${parent_dir}" ]]; then
        echo -e "\n$(date '+%a %d/%b/%Y %H:%M:%S %z') Deleting files older than 1 year from ${parent_dir} (excluding jythonCache/, motorPositions/, .ssh/) ..."
        find_command="${parent_dir} -mindepth 1 -type f -not -path */jythonCache/* -not -path */motorPositions/* -not -path */.ssh/* -mtime +365"
        initial_command=""
        per_file_command="-delete"
        perform_find_and_action
    fi

    # Remove empty directories files from var/
    parent_dir="/dls_sw/${beamline}/var"
    if [[ -d "${parent_dir}" ]]; then
        echo -e "\n$(date '+%a %d/%b/%Y %H:%M:%S %z') Removing empty directories from ${parent_dir} ..."
        find_command="${parent_dir} -mindepth 1 -type d -empty"
        initial_command=""
        per_file_command="-delete"
        perform_find_and_action
    fi

    echo -e "-- end of ${beamline} cleanup\n"
}

#------------------------------------#
#------------------------------------#

