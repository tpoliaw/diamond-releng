# Write job-specific information into a file in the form of name=value pairs
set +x  # Turn off xtrace

properties_filename=${WORKSPACE}/job-specific-environment-variables.properties

cat << EOF >> ${properties_filename}
materialize_component=all-dls-config
EOF

if [[ "${gerrit_single_test}" == "true" || "${gerrit_manual_test}" == "true" ]]; then
  cat << EOF >> ${properties_filename}
build_options_extra=--suppress-compile-warnings
EOF
fi

echo "[gda_create.product_determine-job-specific-properties.sh] wrote ${properties_filename} --->"
cat ${properties_filename}