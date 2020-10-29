# reverse-accessions
Batch job to accession barcodes from SCF into owning IZ

# set up a virtual environment</br>
python3 -m venv venv </br>
source venv/bin/activate

# install the module and requirements
pip install -r requirements.txt

# to run script
python accessions.py <dest_lib_num_code> <barcode_txt_filename>.txt
