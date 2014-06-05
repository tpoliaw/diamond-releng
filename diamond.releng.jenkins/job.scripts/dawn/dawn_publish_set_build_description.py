import os

set_build_description_done = False
try:
    product_build_job = 'Dawn%s.%s-create.product' % (os.environ['Dawn_flavour'], os.environ['Dawn_release'])
    if os.environ['Dawn_release'] == 'master':
        product_build_job_short = 'Dawn%s-create.product' % (os.environ['Dawn_flavour'],)
    else:
        product_build_job_short = '%s-create.product' % (os.environ['Dawn_release'],)
    product_build_number = os.environ['copyartifact_build_number']
    build_description_line_1 = os.environ['product_version_number']
    build_description_line_1 += r'  (x%(platform_count)s) (<a href="/job/%(product_build_job)s/">%(product_build_job_short)s</a> <a href="/job/%(product_build_job)s/%(product_build_number)s/">%(product_build_number)s</a>)' % \
        {'product_build_job': product_build_job, 'product_build_job_short': product_build_job_short, 'product_build_number': product_build_number, 'platform_count': os.environ['platforms_requested']}
    build_description_line_2 = ''
    if os.environ['publish_module_load'] == 'true':
        build_description_line_2 += r', module load'
    if os.environ['publish_webserver_diamond_zip'] == 'true':
        build_description_line_2 += r', diamond .zip'
    if os.environ['publish_webserver_opengda_zip'] == 'true':
        build_description_line_2 += r', opengda .zip'
    if os.environ['publish_p2_site'] == 'true':
        build_description_line_2 += r', p2 site'
    if build_description_line_2:
        print 'set-build-description: %s --> %s' % (build_description_line_1, build_description_line_2[2:])
    else:
        print 'set-build-description: %s (not published anywhere)' % (build_description_line_1,)
    set_build_description_done = True
    break

except Exception as fault:
    print os.path.basename(__file__), 'got exception:', fault

if not set_build_description_done:
    print 'set-build-description: internal error: publish details not determined'
