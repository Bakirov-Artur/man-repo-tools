# -*- coding: utf-8  -*-
# BakirovAR turkin86@mail.ru
import re
import os
import urllib2
import xml.etree.ElementTree as ET
import argparse
import logging
import sys


def download_file(url):
    dl_file = urllib2.urlopen(url)
    return dl_file.read()


def get_links(url):
    html = download_file(url)
    links = re.findall('"((http|ftp)s?://.*?)"', html)
    return [link[0] for link in links]


def ls_links(urls, links_db, sep='/'):
    links = get_links(urls)
    for link in links:
        links_db.append(link)
        if link[-1] == sep:
            ls_links(link, links_db)


def fillter_links(links, filter):
    re_link = re.compile(filter)
    return [link for link in links if re_link.search(link)]


def maven_metadata_to_dict(metadata_list):
    metadata_dict = {}
    for metadata in metadata_list:
        xml_root = ET.fromstring(download_file(metadata))
        groupId = xml_root.find('groupId').text
        artifactId = xml_root.find('artifactId').text
        artifactId_list = metadata_dict.get(artifactId)
        if artifactId_list is None:
            metadata_dict[artifactId] = {'group': [groupId]}
        elif not groupId in artifactId_list.get('group'):
            artifactId_list.get('group').append(groupId)
    return metadata_dict


def get_ext_artifact(links, metadata):
    packaging_type = "zip tar.gz tar ini jar xml".split(' ')
    metadata_ext = metadata.copy()
    for key in metadata_ext.keys():
        artifact_links = fillter_links(links, '/{0}/'.format(key))
        for ptype in packaging_type:
            artifact_ext = fillter_links(artifact_links, '{0}$'.format(ptype))
            artifact_metadata = metadata_ext.get(key)
            artifact_group_tmp = []
            for metadata_group in artifact_metadata.get('group'):
                artifact_group = fillter_links(
                    artifact_ext, '/{0}/'.format(metadata_group.replace(".", '/')))
                if artifact_group:
                    artifact_group_tmp.append(metadata_group + ":" + ptype)
            if artifact_group_tmp:
                artifact_metadata["group"] = artifact_group_tmp
    return metadata_ext


def resolve_artifact(pkg_server, repo_name, artifactId, groupId, pkg_type, version="LATEST"):
    api_resolve_url = "service/local/artifact/maven/resolve"
    resolve_url = 'http://{0}/{1}?r={2}&g={3}&a={4}&v={5}&p={6}'.format(
        pkg_server, api_resolve_url, repo_name, groupId, artifactId, version, pkg_type)
    try:
        return download_file(resolve_url)
    except Exception as e:
        return None


def check_resolve_artifactId(metadata_dict_ext, pkg_server, repo_name):
    keys_dict = metadata_dict_ext.keys()
    for artifactId in keys_dict:
        artifact_groups = metadata_dict_ext.get(artifactId)
        groups = artifact_groups.get('group')
        for group_name in groups:
            # print "group name {0} -> {1}".format(artifactId, group_name)
            groupId, ext = group_name.split(':')
            if resolve_artifact(pkg_server, repo_name, artifactId, groupId, ext):
                # print "remove group {}".format(groups)
                groups.remove(group_name)
        if len(groups) == 0:
            # print "groups 0"
            metadata_dict_ext.pop(artifactId)


def metadata_dict_to_file(metadata_dict_ext, path_file_name):
    with open(path_file_name, "w") as f:
        for artifact_id_name in metadata_dict_ext.keys():
            artifact_groups = metadata_dict_ext.get(artifact_id_name)
            for group_name in artifact_groups.get("group"):
                groupId, ext = group_name.split(':')
                f.write("compile group: '{0}', name: '{1}', version: '+', ext: '{2}'\n".format(
                    groupId, artifact_id_name, ext))


def get_repo_base_url(server_name, scheme="http"):
    return scheme + "://" + server_name + "/content/repositories/"

logging.basicConfig(level=10)
logger = logging.getLogger(os.path.basename(__file__))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Files dump')
    parser.add_argument('--src_pkg_server',
                        help='src_pkg.server.com', required=True)
    parser.add_argument('--dst_pkg_server',
                        help='dst_pkg.server.com', required=False)
    parser.add_argument('--src_repo', help='release_dev', required=True)
    parser.add_argument('--dst_repo', help='release_test', required=True)
    parser.add_argument(
        '--out_dep_file', help='/your/path/file/name', required=True)

    arguments = parser.parse_args(sys.argv[1:])
    # Varibles

    link_list = []

    src_repo_url = get_repo_base_url(
        arguments.src_pkg_server) + arguments.src_repo

    dst_repo = arguments.dst_repo
    dst_pkg_server = arguments.dst_pkg_server or arguments.src_pkg_server

    # Prepare src
    logger.info('Preparing the source repository:\n{0}'.format(src_repo_url))
    ls_links(src_repo_url, link_list)

    link_list = sorted(set(link_list))
    maven_metadata_list = fillter_links(link_list, 'maven-metadata.xml$')

    metadata_dict = maven_metadata_to_dict(maven_metadata_list)

    metadata_dict_ext = get_ext_artifact(link_list, metadata_dict)

    # check artifactId in dst_repo
    logger.info('Checking destination repository')
    check_resolve_artifactId(metadata_dict_ext, dst_pkg_server, dst_repo)
    dep_file_name = arguments.out_dep_file
    logger.info('Save resolve to file: {0}'.format(dep_file_name))
    metadata_dict_to_file(metadata_dict_ext, dep_file_name)

# Esay start example
# python wls.py --src_pkg_server "pkg-ttm.moex.com" --src_repo "snapshots" --dst_repo "SPECTRA65_drop1" --out_dep_file "./sda.txt"
