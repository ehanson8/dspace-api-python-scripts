import csv
import datetime
import glob
import json
import logging
import os
import time

import click
import structlog

from dsaps import models

logger = structlog.get_logger()


@click.group()
@click.option('--url', envvar='DSPACE_URL')
@click.option('-e', '--email', prompt='Enter email',
              help='The email of the user for authentication.')
@click.option('-p', '--password', prompt='Enter password',
              envvar='TEST_PASS', hide_input=True,
              help='The password for authentication.')
@click.pass_context
def main(ctx, url, email, password):
    ctx.obj = {}
    dt = datetime.datetime.utcnow().isoformat(timespec='seconds')
    log_suffix = f'{dt}.log'
    structlog.configure(processors=[
                        structlog.stdlib.filter_by_level,
                        structlog.stdlib.add_log_level,
                        structlog.stdlib.PositionalArgumentsFormatter(),
                        structlog.processors.TimeStamper(fmt="iso"),
                        structlog.processors.JSONRenderer()
                        ],
                        context_class=dict,
                        logger_factory=structlog.stdlib.LoggerFactory())
    logging.basicConfig(format="%(message)s",
                        handlers=[logging.FileHandler(f'logs/log-{log_suffix}',
                                  'w')],
                        level=logging.INFO)
    logger.info('Application start')
    client = models.Client(url)
    client.authenticate(email, password)
    start_time = time.time()
    ctx.obj['client'] = client
    ctx.obj['start_time'] = start_time


@click.group()
def aux():
    pass


@main.command()
@click.option('-f', '--field', prompt='Enter the field to be searched',
              help='The field to search.')
@click.option('-s', '--string', prompt='Enter the string',
              help='The field to search.')
@click.option('-t', '--search_type', prompt='Enter the type of search',
              help='The type of search.',
              type=click.Choice(['exists', 'doesnt_exist', 'equals',
                                 'not_equals', 'contains', 'doesnt_contain']),
              default='contains')
@click.pass_context
def search(ctx, field, string, search_type):
    # Temp function for testing
    client = ctx.obj['client']
    start_time = ctx.obj['start_time']
    item_links = client.filtered_item_search(field, string, search_type)
    logger.info(item_links)
    models.elapsed_time(start_time, 'Elapsed time')


@main.command()
@click.option('-c', '--comm_handle', prompt='Enter the community handle',
              help='The handle of the community in which to create the ,'
              'collection.')
@click.option('-n', '--coll_name', prompt='Enter the name of the collection',
              help='The name of the collection to be created.')
@click.option('-m', '--metadata', prompt='Enter the path of the metadata file',
              help='The path of the JSON file of metadata.')
@click.option('-f', '--file_path', prompt='Enter the path',
              help='The path of the content, a URL or local drive path.')
@click.option('-t', '--file_type', prompt='Enter the file type',
              help='The file type to be uploaded.')
@click.option('-i', '--ingest_type', prompt='Enter the type of ingest',
              help='The type of ingest to perform: local, remote.',
              type=click.Choice(['local', 'remote']))
@click.pass_context
def newcoll(ctx, comm_handle, coll_name, metadata, file_path, file_type,
            ingest_type):
    client = ctx.obj['client']
    start_time = ctx.obj['start_time']
    with open(metadata, encoding='UTF-8') as fp:
        coll_metadata = json.load(fp)
        coll_id = client.post_coll_to_comm(comm_handle, coll_name)
        file_dict = {}
        if ingest_type == 'local':
            files = glob.glob(f'{file_path}/**/*.{file_type}', recursive=True)
            for file in files:
                file_name = os.path.splitext(os.path.basename(file))[0]
                file_dict[file_name] = file
        elif ingest_type == 'remote':
            file_dict = models.build_file_dict_remote(file_path, file_type,
                                                      file_dict)
        items = client.post_items_to_coll(coll_id, coll_metadata, file_dict,
                                          ingest_type)
        for item in items:
            logger.info(f'Item posted: {item}')
    models.elapsed_time(start_time, 'Total runtime:')


@aux.command()
@click.option('-m', '--metadata_csv', prompt='Enter the metadata CSV file',
              help='The path of the CSV file of metadata.')
@click.option('-f', '--file_path', prompt='Enter the path',
              help='The path of the content, a URL or local drive path.')
@click.option('-t', '--file_type', prompt='Enter the file type',
              help='The file type to be uploaded.')
def reconcile(metadata_csv, file_path, file_type):
    if file_path.startswith('http'):
        file_dict = models.build_file_dict_remote(file_path, file_type, {})
    else:
        files = glob.glob(f'{file_path}/**/*.{file_type}', recursive=True)
        for file in files:
            file_name = os.path.splitext(os.path.basename(file))[0]
            file_dict[file_name] = file
    metadata_ids = []
    with open(metadata_csv) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            value = row['file_identifier']
            metadata_ids.append(value)
    file_matches = []
    file_ids = []
    for file_id, v in file_dict.items():
        file_ids.append(file_id)
        for metadata_id in [m for m in metadata_ids if file_id == m]:
            file_matches.append(file_id)
    metadata_matches = []
    for metadata_id in metadata_ids:
        for file_id in file_dict:
            if file_id == metadata_id:
                metadata_matches.append(metadata_id)
    no_files = set(metadata_ids) - set(metadata_matches)
    no_metadata = set(file_ids) - set(file_matches)
    models.create_csv_from_list(no_metadata, 'no_metadata.csv')
    models.create_csv_from_list(no_files, 'no_files.csv')
    models.create_csv_from_list(metadata_matches, 'metadata_matches.csv')


@aux.command()
@click.option('-m', '--metadata_csv', prompt='Enter the metadata CSV file',
              help='The path of the CSV file of metadata.')
def metadatajson(metadata_csv):
    with open(metadata_csv) as csvfile:
        reader = csv.DictReader(csvfile)
        metadata_group = []
        mapping_dict = {'fileIdentifier': ['file_identifier'],
                        'dc.contributor.author': ['author name - direct'],
                        'dc.contributor.advisor': ['supervisor(s)'],
                        'dc.date.issued': ['pub date'],
                        'dc.description.abstract': ['Abstract', 'en_US'],
                        'dc.title': ['Title', 'en_US'],
                        'dc.relation.ispartofseries': ['file_identifier']}
        for row in reader:
            metadata_rec = []
            metadata_rec = models.create_metadata_rec(mapping_dict, row,
                                                      metadata_rec)
            metadata_rec.append({'key': 'dc.format.mimetype', 'language':
                                'en_US', 'value': 'application/pdf'})
            metadata_rec.append({'key': 'dc.language.iso', 'language':
                                'en_US', 'value': 'en_US'})
            metadata_rec.append({'key': 'dc.publisher', 'language': 'en_US',
                                 'value': 'Massachusetts Institute of '
                                 'Technology. Laboratory for Computer'
                                 'Science'})
            metadata_rec.append({'key': 'dc.rights', 'language': 'en_US',
                                'value': 'Educational use permitted'})
            metadata_rec.append({'key': 'dc.rights.uri', 'language': 'en_US',
                                 'value': 'http://rightsstatements.org/vocab/'
                                 'InC-EDU/1.0/'})
            metadata_rec.append({'key': 'dc.type', 'language': 'en_US',
                                'value': 'Technical Report'})
            item = {'metadata': metadata_rec}
            metadata_group.append(item)
    file_name = os.path.splitext(os.path.basename(metadata_csv))[0]
    with open(f'{file_name}.json', 'w') as f:
        json.dump(metadata_group, f)


cli = click.CommandCollection(sources=[main, aux])

if __name__ == '__main__':
    cli()
