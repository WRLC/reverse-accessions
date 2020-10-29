import time
import requests
import sys
import xml.etree.ElementTree as ET
import logging

from settings import *

#  Overriding sys.argv[]s for testing
UPDATE_IZ = sys.argv[1]  #
SOURCE_IZ = '4617'  # SCF PROD
REPORT_FILE = sys.argv[2]
FROM_IZ_KEY = SOURCE_IZ_KEYS[SOURCE_IZ]  # SCF Read Key
UPDATE_IZ_KEY = IZ_READ_WRITE_KEYS[UPDATE_IZ]  # Dest R/W key

DEFAULTS_UPDATE_IZ = DEFAULTS_IN_UPDATE_IZ[UPDATE_IZ]

# Alma API routes
GET_BY_BARCODE = '/almaws/v1/items?item_barcode={}'
GET_BIB_BY_NZ_MMS = '/almaws/v1/bibs?nz_mms_id={}'
GET_BIB_BY_MMS = '/almaws/v1/bibs?mms_id={}'
CREATE_BIB = '/almaws/v1/bibs?from_nz_mms_id={}'
GET_HOLDINGS_LIST = '/almaws/v1/bibs/{mms_id}/holdings'
GET_HOLDING = '/almaws/v1/bibs/{mms_id}/holdings/{holding_id}'
CREATE_HOLDING = '/almaws/v1/bibs/{mms_id}/holdings'
GET_ITEMS_LIST = '/almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items'
CREATE_ITEM = '/almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items'

# setting up Dest IZ vars to use
dest_get_params = {'apikey': UPDATE_IZ_KEY}
dest_headers = {'Content-type': 'application/xml',
                'Authorization': 'apikey ' + UPDATE_IZ_KEY}
dest_headers_apionly = {'Authorization': 'apikey ' + UPDATE_IZ_KEY}

# HOLDINGS TEMPLATE - used to create holdings record for SCF
HOLDINGS_TEMPLATE = b'''<holding><record><leader>#####nx##a22#####1n#4500</leader><controlfield tag="008">1011252u####8###4001uueng0000000</controlfield><datafield ind1="0" ind2=" " tag="852"><subfield code="b"></subfield><subfield code="c"></subfield><subfield code="h"></subfield><subfield code="i"></subfield></datafield></record></holding>'''

# Additional elements for records
EIGHT_FIVE_TWO_SUB_B = ".//record/datafield[@tag='852']/subfield[@code='b']"
EIGHT_FIVE_TWO_SUB_C = ".//record/datafield[@tag='852']/subfield[@code='c']"
EIGHT_FIVE_TWO_SUB_H = ".//record/datafield[@tag='852']/subfield[@code='h']"
EIGHT_FIVE_TWO_SUB_I = ".//record/datafield[@tag='852']/subfield[@code='i']"


def read_report_generator(report):
    cnt = 0
    with open(report) as fh:
        for barcode in fh:
            barcode = barcode.rstrip('\n')
            cnt += 1
            yield barcode
    print('Number of barcodes read = ', cnt)


def main():
    # Setting up logging to catch problem barcodes and other issues
    logfile = UPDATE_IZ + 'ACC' + SOURCE_IZ + 'log.' + time.strftime('%m%d%H%M', time.localtime())
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    lh = logging.FileHandler(logfile)
    lh.setFormatter(formatter)
    logging.getLogger().addHandler(lh)
    logging.getLogger().setLevel(logging.DEBUG)  # Extreme debug
    # logging.getLogger().setLevel(logging.WARNING)   #  Setting for reporting
    # logging.getLogger().setLevel(logging.INFO)      #  Setting for debugging

    # Initialize Counts for report
    items_read = 0
    items_created = 0
    items_present = 0
    items_missing = 0

    logging.warning('Name of File used, ' + REPORT_FILE)

    for barcode in read_report_generator(REPORT_FILE):
        items_read += 1
        logging.warning('PROCESSING BARCODE, ' + barcode)

        print('Processing item ' + str(items_read) + ' bc=' + barcode)

        # step one, retrieve by barcode from SCF
        r_owner_master_record = requests.get(ALMA_SERVER + GET_BY_BARCODE.format(barcode),
                                             params={'apikey': FROM_IZ_KEY})

        if r_owner_master_record.status_code != requests.codes.ok:
            items_missing += 1
            # break from processing this barcode in  loop
            # log barcode with message for importer to check
            logging.warning('No match for barcode = ' + barcode)
            logging.info(r_owner_master_record.text)
            continue

        # Set up xml root tree so we can parse for data
        root = ET.fromstring(r_owner_master_record.content)

        # Get item/bib_data/mms_id
        local_mms_id = root.find('./bib_data/mms_id').text
        print('local_mms_id = ' + local_mms_id)

        # Get item/holding_data/holding_id & location
        holding_id = root.find('./holding_data/holding_id').text
        logging.info('holding id = ' + holding_id)
        location = DEFAULTS_UPDATE_IZ['loc']
        loc_desc = DEFAULTS_UPDATE_IZ['ldesc']
        logging.debug('location = ' + location)
        logging.debug('loc desc = ' + loc_desc)

        # Get item/item_data/pid
        pid = root.find('./item_data/pid').text
        logging.info('pid = ' + pid)

        # Get the physical_material_type - need to check later
        physical_material_type = root.find('./item_data/physical_material_type').text
        logging.info('physical_material_type = ' + physical_material_type)

        # Create new item record but remove pid and physical_material_type if neccesary
        new_item_record = ET.fromstring(b'<item></item>')
        item_data = root.find('./item_data')
        pid_element = item_data.find('pid')
        item_data.remove(pid_element)

        # Remove SCF Provenance element
        provenance_element = item_data.find('provenance')
        item_data.remove(provenance_element)

        # Set destination location
        library_element = item_data.find('library')
        library_element.text = DEFAULTS_UPDATE_IZ['library']
        library_element.set('desc', DEFAULTS_UPDATE_IZ['libdesc'])

        logging.info('lib_ele desc = ' + library_element.text)

        # Do I need to get the description of location in real time?  Perhaps a look up table will do
        location_element = item_data.find('location')
        location_element.text = location
        if location_element != '':
            location_element.set('desc', loc_desc)

        # Get circ policy for Destination IZ
        policy_element = item_data.find('policy')
        policy_element.text = DEFAULTS_UPDATE_IZ['itempolicy']
        policy_element.set('desc', DEFAULTS_UPDATE_IZ['idesc'])
        # policy_element.text = 'GT circ'
        # policy_element.set('desc', 'GT default')

        #  Perhaps do more mapping of material type to Item policy above (ISSUE=perl?)
        if physical_material_type == 'ELEC':
            for physical_material_type in item_data.iter('physical_material_type'):
                physical_material_type.text = str('OTHER')
                physical_material_type.set('desc', 'Other')
                logging.warning('Check material type for BC =' + barcode)
        new_item_record.append(item_data)
        # logging.info('ABOUT to DUMP new item record')
        # ET.dump(new_item_record)

        nz_mms_id = 0
        for item in root.findall('./bib_data/network_numbers/network_number'):
            logging.debug('NZ_mms_id = ' + item.text)
            if item.text.find('WRLC_NETWORK') != -1:
                logging.debug('good one = ' + item.text[22:])
                nz_mms_id = item.text[22:]
                logging.warning('nz_mms_id = ' + nz_mms_id)

        # Check that NZ bib exists, if not stop and report
        if nz_mms_id == 0:
            logging.info('No NZ Bib record for barcode = ' + barcode)
            continue

        dest_mms_id = 0
        r_dest_bib = requests.get(ALMA_SERVER + GET_BIB_BY_NZ_MMS.format(nz_mms_id), params=dest_get_params)

        time.sleep(2)  # added when conn closed problem

        if r_dest_bib.status_code == requests.codes.ok:
            # We have a bib record in destination IZ
            dest_bib_content = ET.fromstring(r_dest_bib.content)
            dest_mms_id = dest_bib_content.find('./bib/mms_id').text
            logging.warning('We already have dest_mms_id = ' + dest_mms_id)
            logging.warning('dest bib record = ' + r_dest_bib.url)
        else:
            logging.info('We need to create bib' + r_dest_bib.text)

            #  Create a bib record for destination IZ
            empty_bib = b'<bib />'
            r_create_bib = requests.post(ALMA_SERVER + CREATE_BIB.format(nz_mms_id), headers=dest_headers,
                                         data=empty_bib)
            time.sleep(5)
            # Get new bib with the destination IZs mms_id
            if r_create_bib.status_code == requests.codes.ok:
                r_dest_bib = requests.get(ALMA_SERVER + GET_BIB_BY_NZ_MMS.format(nz_mms_id), params=dest_get_params)

                time.sleep(2)  # added when Conn closed problem

                if r_dest_bib.status_code == requests.codes.ok:
                    # We have a bib record in destination IZ
                    dest_bib_content = ET.fromstring(r_dest_bib.content)
                    dest_mms_id = dest_bib_content.find('./bib/mms_id').text
                    logging.info('newly created mms_id = ' + dest_mms_id)
                else:
                    logging.warning('Could not create destination IZ bib record for BC = ', barcode)
                    continue

        #  Need to check if there is a holding record with item's location in SCF

        r_dest_holding = requests.get(ALMA_SERVER + GET_HOLDINGS_LIST.format(mms_id=dest_mms_id),
                                      params=dest_get_params)

        time.sleep(5)  # added when Conn closed problem

        logging.info('dest holdings url = ' + r_dest_holding.url)
        dest_hold_list = ET.fromstring(r_dest_holding.content)

        #  Need to iterate through list, search for location match to get holding_id
        dest_holding_id = 0
        for child in dest_hold_list:
            if child.tag == 'holding':
                logging.info('looking for loc = ' + location)
                if child.find('location').text == location:
                    logging.info('Holding ID:')
                    logging.info(child.find('holding_id').text)
                    dest_holding_id = child.find('holding_id').text
                    break
                else:
                    logging.info("Could not find holding in list for barcode, " + barcode)

        # Get holding information from local IZ if not present in destination IZ
        if dest_holding_id == 0:
            r_local_holding = requests.get(ALMA_SERVER + GET_HOLDING.format(mms_id=local_mms_id, holding_id=holding_id),
                                           params={'apikey': FROM_IZ_KEY})

            time.sleep(2)  # added when Conn closed problem

            local_holding = r_local_holding.content
            logging.info('local holding = ' + r_local_holding.text)

            # parse owning holdings record
            scf_holdings_record = ET.fromstring(local_holding)

            # extract 852 information
            if scf_holdings_record.find(EIGHT_FIVE_TWO_SUB_H) is None:
                eight52_h = str("")
            else:
                eight52_h = scf_holdings_record.find(EIGHT_FIVE_TWO_SUB_H).text
            if scf_holdings_record.find(EIGHT_FIVE_TWO_SUB_I) is None:
                eight52_i = str('')
            else:
                eight52_i = scf_holdings_record.find(EIGHT_FIVE_TWO_SUB_I).text

            # Create empty holding record from template
            new_holdings_record = ET.fromstring(HOLDINGS_TEMPLATE)

            # Now insert the owning call number
            new_holdings_record.find(EIGHT_FIVE_TWO_SUB_H).text = eight52_h
            new_holdings_record.find(EIGHT_FIVE_TWO_SUB_I).text = eight52_i
            new_holdings_record.find(EIGHT_FIVE_TWO_SUB_C).text = location
            new_holdings_record.find(EIGHT_FIVE_TWO_SUB_B).text = DEFAULTS_UPDATE_IZ['library']

            # ET.dump(new_holdings_record)

            payload = ET.tostring(new_holdings_record, encoding='UTF-8')
            logging.info('new holdings payload = ' + payload.decode('UTF-8'))

            # Create/Post the new holding record in the SCF    ##### Uncomment
            new_holding = requests.post(ALMA_SERVER + CREATE_HOLDING.format(mms_id=dest_mms_id), headers=dest_headers,
                                        data=payload)
            time.sleep(5)
            if new_holding.status_code == requests.codes.ok:
                logging.info('new hold content = ' + new_holding.text)

                new_dest_hold_record = ET.fromstring(new_holding.content)
                dest_holding_id = new_dest_hold_record.find('holding_id').text
                logging.info('new dest_holding_id = ' + dest_holding_id)
            else:
                logging.warning('No holding created for barcode, ' + barcode)
                continue

        #  End if no holdings that match in SCF

        #  At this point we should have a scf bib and a location matching holding record

        #  Check to see if item has already been created

        dest_item_record = requests.get(
            ALMA_SERVER + GET_ITEMS_LIST.format(mms_id=dest_mms_id, holding_id=dest_holding_id), params=dest_get_params)

        time.sleep(2)  # added when Conn closed problem

        dest_item_list = ET.fromstring(dest_item_record.content)

        #  Need to iterate through list to see if there is an item record.  If empty,
        #  Need to create the item.  If not, do we need to update the item record?
        item_exists = 0
        for child in dest_item_list.iter('barcode'):
            if child.text == barcode:
                logging.info('item is already in Destination IZ')
                logging.info(barcode + ' does not need to be added.')
                item_exists = 1  # flag
                items_present += 1  # counter
                break

        #  Create the new item record in the SCF
        if item_exists == 0:
            payload = ET.tostring(new_item_record, encoding='UTF-8')
            logging.info('new item record = ' + payload.decode('UTF-8'))

            new_dest_item = requests.post(
                ALMA_SERVER + CREATE_ITEM.format(mms_id=dest_mms_id, holding_id=dest_holding_id), headers=dest_headers,
                data=payload)
            time.sleep(5)
            if new_dest_item.status_code != requests.codes.ok:
                logging.warning('A new item was not created, bc =  ' + barcode)
                items_present += 1
            else:
                new_dest_item_record = ET.fromstring(new_dest_item.content)
                items_created += 1

    #  Need to test for correct submission
    #  if correct increment counter
    #  This should be end of processing - continue the loop.

    #  Report at end
    logging.warning('Items created = ' + str(items_created))
    logging.warning('Items already present = ' + str(items_present))
    logging.warning('Items not found/processed = ' + str(items_missing))
    logging.warning('Total items read from file = ' + str(items_read))


if __name__ == '__main__':
    main()
