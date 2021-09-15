import csv
import re
import os
import gzip
import tempfile
import json
import pandas as pd
from typing import Dict, List, Optional, IO
from collections import defaultdict
from zipfile import ZipFile, BadZipFile

from eco_kg.transform_utils.transform import Transform
from eco_kg.utils.transform_utils import parse_header, parse_line, write_node_edge_item
from eco_kg.utils import biohub_converter as bc
from eco_kg.utils.robot_utils import *
from eco_kg.utils.transform_utils import unzip_to_tempdir
from kgx.cli.cli_utils import transform
"""
Ingest traits dataset (EOL TraitBank)

Essentially just ingests and transforms this file:
https://editors.eol.org/other_files/SDR/traits_all.zip

And extracts the following columns:
    - 
"""

class EOLTraitsTransform(Transform):

    def __init__(self, input_dir: str = None, output_dir: str = None) -> None:
        source_name = 'EOLTraitbank'
        super().__init__(source_name, input_dir, output_dir)  # set some variables
        self.node_header = ['id','name','category','has_attribute','has_attribute_type','provided_by'] #can I add node properties?
        self.edge_header = ['subject','predicate','object','relation','has_attribute','has_attribute_type','has_quantitative_value','has_unit','has_qualitative_value','provided_by']

    def run(self, EOLTraitbank: Optional[str] = None) -> None:
        """Method is called and performs needed transformations to process the 
        trait data (EOL Traitbank)
        
        Args:
            EOL_Traitbank: entire contents of EOL TraitBank [EOLTraitbank.zip]
        """
        if not EOLTraitbank:
            EOLTraitbank = os.path.join(self.input_base_dir, 'EOLTraitbank.zip')
        seen_node: dict = defaultdict(int)
        seen_edge: dict = defaultdict(int)
        # Nodes
        org_node_type = "biolink:OrganismTaxon" 
        trait_node_type = 'biolink:PhenotypicFeature'
        env_node_type = 'biolink:GeographicLocation'
        chem_node_type = 'biolink:ChemicalEntity'

        #Prefixes
        org_prefix = "EOL:"
        env_prefix = "ENVO:"

        # Edges
        org_to_trait_edge_label = "biolink:has_phenotype" 
        org_to_trait_edge_relation = "RO:0002200"
        org_to_parent_edge_label = 'biolink:subclass_of'
        org_to_parent_edge_relation = 'RO:'
        org_to_org_edge_label = "biolink:interacts_with"
        org_to_org_edge_relation = "RO:0002434"
        org_to_env_edge_label = "biolink:located_in"
        org_to_env_edge_relation = "RO:0001025"
        org_to_chem_edge_label = 'biolink:produces'
        org_to_chem_edge_relation = 'RO:0003000'

        # unzip files and make dataframes
        listOfFileNames = ['terms.csv','pages.csv','traits.csv']
        #zip still isn't working. Error is zipfile.BadZipFile: Bad CRC-32 for file 'trait_bank/traits.csv'
#        with ZipFile('data/raw/EOLtraitbank.zip', 'r', allowZip64=True) as zf:
#            print('Unzipping files now')
#            zf.extractall(path='data/')
#            for fn in listOfFileNames:
#                print(fn)
#                try:
#                    zf.extract(fn)
#                except BadZipFile:
#                    print(fn + ' did not work')
#            print('Done')
        with open(os.path.join(self.input_base_dir, 'eol_trait_ids.txt'), 'r') as et:
            eol_trait_ids = json.load(et)

        plant_ids = ['1115166','52189015','583954','1115098','1276830','52513595','5826531','5826532','1294015','5826551','5826557',
        '5826558','5826581','52315112','50576657','58265934','5826602','5826619','1115168','5826627','5797072','5796643','5826634',
        '5826643','5826646','2897040','5796630','1115577','5797315','51844552','5797605','5826554','5797663','5826757','11305471',
        '1114074','1114075','1115260','5820148','1115261','49106130','5142500','5142507','5142508','50151868','5142514','5142525',
        '5142534','5142538','5142551','16986546','5824503','1115582','5824504','49910160','5824510','1115583','5824489','1115099',
        '5824530','1115584','5824499','2896805','5824549','2896806','1115872','5824569','1115470','5824572','592441','584256',
        '584296','584262','584261','466982','466983','466984','483052','485707','584254','584257','584258','584259','584260',
        '584263','584264','584265','584266','585453','585456','585457','585458','592440','1276832','2871964','2871965','2871966',
        '2871968','2871971','2871972','2871973','2871975','2871976','2871977','2871978','2871979','2871980','2871981','2871982',
        '2871983','2871984','2871985','2871986','2871988','2871990','2871991','2871992','2871993','2871995','2871996','2871997',
        '2871998','2872000','2872002','2872003','2872007','2872009','2872010','2872011','2872012','2872013','2872014','2872015',
        '2899494','2899495','2899496','2899497','2899498','2899499','2899500','2899501','2899502','2899503','5603205','5603266',
        '5603289','5603345','5603356','5603368','5603383','5603393','5603535','11203931','19844026','19844100','26336982','47108509',
        '47108511','47108513','47108515','47108516','47108519','47108524','47108525','47108532','47108533','47281634','48906594',
        '48432002','49153210','49905063','52201053','50930145','52201060','49905066','52549626','52549621','52549624','52549615',
        '52201061','50197387','51846554','50197413','52549634','52549614','52337463','52201040','52549617','52549632','52549633',
        '52549616','51846562','51846559','52549620','50197541','52549623','52549628','49905070','52549613','49997307','52201059',
        '52549629','51846566','50197427','52549619','52549625','52549627','52549636','52549635']
        location_uris = ['http://rs.tdwg.org/dwc/terms/habitat','http://eol.org/schema/terms/Present',
        'http://eol.org/schema/terms/NativeRange','http://eol.org/schema/terms/IntroducedRange',
        'http://purl.obolibrary.org/obo/RO_0002303','https://eol.org/schema/terms/cultivated_in',
        'http://purl.allotrope.org/ontologies/property#AFX_0000939','http://eol.org/terms/endemic',
        'http://eol.org/schema/terms/InvasiveRange','https://www.wikidata.org/entity/Q295469']
        skip = ['http://eol.org/schema/terms/SoilRequirements','http://eol.org/schema/terms/TypeSpecimenRepository',
        'http://eol.org/schema/terms/Uses','http://rs.tdwg.org/ontology/voc/SPMInfoItems#ConservationStatus',
        'http://eol.org/schema/terms/CommercialAvailability','http://eol.org/schema/terms/population_trend',
        'http://eol.org/schema/terms/FruitSeedColor','http://eol.org/schema/terms/FruitPersistence',
        'http://eol.org/schema/terms/FuelwoodSuitability','http://eol.org/schema/terms/GerminationRequirements',
        'http://eol.org/schema/terms/GrainType','http://eol.org/schema/terms/GrassGrowthType',
        'http://sweet.jpl.nasa.gov/2.3/humanAgriculture.owl#Horticulture','http://eol.org/schema/terms/BloatPotential',
        'http://eol.org/schema/terms/PropagationMethod','http://eol.org/schema/terms/PostFireSeedlingEmergence',
        'http://eol.org/schema/terms/ResproutAbility','http://purl.obolibrary.org/obo/FLOPO_0900022',
        'http://purl.obolibrary.org/obo/FLOPO_0007484','http://purl.obolibrary.org/obo/TO_0000624',
        'http://top-thesaurus.org/annotationInfo?viz=1&trait=Woodiness']
        with open(self.output_node_file, 'w') as node, \
            open(self.output_edge_file, 'w') as edge:
            node.write("\t".join(self.node_header) + "\n")
            edge.write("\t".join(self.edge_header) + "\n")
            for filename in listOfFileNames:
                if filename.startswith('.'):
                    print(f"skipping file {filename}")
                    continue
                path = 'data/raw/trait_bank/'
                file = path + filename
                with open(file, 'r') as f:
                    if filename == 'pages.csv':
                        #populus = []
                        my_df = []
                        next(f)
                        for line in f:
                            row = line.strip('\n').split(',')
                            page_id = row[0]
                            parent_id = row[1]
#                            if parent_id == '11896897' and page_id not in populus:
#                                populus.append(page_id)
                            if page_id in plant_ids or parent_id in plant_ids:
                                d = {
                                    'page_id':page_id,
                                    'parent_id':parent_id,
                                    'rank':row[2],
                                    'canonical':row[3]
                                    }
                                my_df.append(d)
                        pages_df = pd.DataFrame(my_df)
                        print(file)
                        print(len(my_df))
                        print(len(pages_df))
                        list_of_taxa = pages_df['page_id'].to_list()
#                        print(populus)
                    if filename == 'traits.csv':
                        my_df = []
                        next(f)
                        for row in csv.reader(f, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL):
                            page_id = row[1]
                            if page_id in list_of_taxa:
                                d = {
                                'eol_pk':row[0],'page_id':row[1],'resource_pk':row[2],'resource_id':row[3],
                                'citation':row[0],'source':row[4],'predicate':row[6],'object_page_id':row[7],
                                'value_uri':row[8],'normal_measurement':row[9],'normal_units_uri':row[10],
                                'normal_units':row[11],'measurement':row[12],'units_uri':row[13],'units':row[14],
                                'literal':row[15],'method':row[16],'remarks':row[17],'sample_size':row[18],'name_en':row[19],
                                }
                                my_df.append(d)
                        traits_df = pd.DataFrame(my_df)
                        print(file)
                        print(len(my_df))
                        print(len(traits_df))
                        list_of_traits = traits_df['eol_pk'].to_list()
                        #traits_df.to_csv('filtered_traits.txt')
                    if filename == 'metadata.csv':
                        my_df = []
                        next(f)
                        for line in f:
                            row = line.strip('\n').split(',')
                            trait_pk = row[1]
                            metadata_pk = row[0]
                            if trait_pk in list_of_traits and 'Trait' in metadata_pk:
                                d = {
                                'eol_pk':row[0],'trait_eol_pk':row[1],'predicate':row[2],'value_uri':row[3],
                                'measurement':row[4],'units_uri':row[5],'literal':row[6]
                                }
                                my_df.append(d)
                        metadata_df = pd.DataFrame(my_df)
                        print(file)
                        print(len(my_df))
                        print(len(metadata_df))
                        metadata_df.to_csv('filtered_metadata.txt')
                    if filename == 'inferred.csv':
                        my_df = []
                        next(f)
                        for line in f:
                            row = line.strip('\n').split(',')
                            page_id = row[0]
                            if page_id in list_of_taxa:
                                d = {
                                'page_id':row[0],
                                'inferred_trait':row[1]
                                }
                                my_df.append(d)
                        inferred_df = pd.DataFrame(my_df)
                        print(file)
                        print(len(my_df))
                        print(len(inferred_df))
                    if filename == 'terms.csv':
                        #df = pd.read_csv(file, sep=',', low_memory=False, header=0)
                        #terms_df = df[['uri','name','type']]
                        next(f)
                        trait_labels = {}
                        for line in f:
                            row = line.strip('\n').split(',')
                            mtype = row[2]
                            uri = row[0]
                            name = row[1]
                            if uri not in trait_labels:
                                d = {
                                "label":name,
                                "type":mtype
                                }
                                trait_labels[uri] = d
                            if name not in trait_labels:
                                d = {
                                "uri":uri,
                                "type":mtype
                                }
                                trait_labels[name] = d
                        print(file)
                        #print(trait_labels)
        
            # transform
            #write nodes and edges from pages dataframe
            for index, row in pages_df.iterrows():
                org_id = org_prefix + str(row['page_id'])
                label = row['canonical']
                rank = row['rank']
                provided_by = 'EOL'
                has_attribute = rank
                has_attribute_type = ''
                parent_id = org_prefix + str(row['parent_id'])
                #write organism nodes
                if org_id not in seen_node:
                    write_node_edge_item(fh=node,
                                         header=self.node_header,
                                         data=[org_id,
                                               label,
                                               org_node_type,
                                               has_attribute,
                                               has_attribute_type,
                                               provided_by])
                    seen_node[org_id] += 1
                if parent_id not in seen_node:
                    label = ''
                    has_attribute = ''
                    has_attribute_type = ''
                    write_node_edge_item(fh=node,
                                         header=self.node_header,
                                         data=[parent_id,
                                               label,
                                               org_node_type,
                                               has_attribute,
                                               has_attribute_type,
                                               provided_by])
                    seen_node[parent_id] += 1
                #write parent/child edges
                if org_id+parent_id not in seen_edge:
                    has_attribute = ''
                    has_attribute_type = ''
                    has_quantitative_value = ''
                    has_unit = ''
                    has_qualitative_value = ''
                    write_node_edge_item(fh=edge,
                                            header=self.edge_header,
                                            data=[org_id,
                                                org_to_parent_edge_label,
                                                parent_id,
                                                org_to_parent_edge_relation,
                                                has_attribute,
                                                has_attribute_type,
                                                has_quantitative_value,
                                                has_unit,
                                                has_qualitative_value,
                                                provided_by])
                    seen_edge[org_id+parent_id] += 1

            # Write nodes and edges from traits dataframe
            for index, row in traits_df.iterrows():
                #ignoring sample size for the moment
#                if row['sample_size'] != '':
#                    print(row)
                trait_id = row['eol_pk']
                trait_uri = row['predicate']
                org_id = org_prefix + row['page_id']
                provided_by = row['resource_id'] + '-EOL'
                if trait_uri not in location_uris and trait_uri not in skip and trait_labels[trait_uri]['type'] == 'measurement':
                    try:
                        trait_label = eol_trait_ids[trait_uri]['label']
                        trait_curie = eol_trait_ids[trait_uri]['curie']
                        #print(trait_curie)
                    except KeyError:
                        print('need to add a trait to the dictionary 3')
                        print(row)
                    #write produces node
                    if trait_uri == 'http://purl.obolibrary.org/obo/RO_0003000':
                        trait_uri = row['value_uri']
                        try:
                            trait_label = eol_trait_ids[trait_uri]['label']
                            trait_curie = eol_trait_ids[trait_uri]['curie']
                        except KeyError:
                            print('need to add a trait to the dictionary 4')
                            print(row)
                        if trait_uri not in seen_node:
                            has_attribute = ''
                            has_attribute_type = ''
                            write_node_edge_item(fh=node,
                                                 header=self.node_header,
                                                 data=[trait_curie,
                                                       trait_label,
                                                       chem_node_type,
                                                       has_attribute,
                                                       has_attribute_type,
                                                       provided_by])
                            seen_node[trait_uri] += 1
                        #write produces edge
                        if trait_id not in seen_edge:
                            has_attribute_type = ""
                            has_quantitative_value = ""
                            has_unit = ""
                            has_qualitative_value = ""
                            write_node_edge_item(fh=edge,
                                                 header=self.edge_header,
                                                 data=[org_id,
                                                       org_to_chem_edge_label,
                                                       trait_curie,
                                                       org_to_chem_edge_relation,
                                                       trait_label,
                                                       has_attribute_type,
                                                       has_quantitative_value,
                                                       has_unit,
                                                       has_qualitative_value,
                                                       provided_by])
                            seen_node[trait_id] += 1
                        continue
                    #write trait node
                    if trait_uri not in seen_node:
                        has_attribute = ''
                        has_attribute_type = ''
                        write_node_edge_item(fh=node,
                                             header=self.node_header,
                                             data=[trait_curie,
                                                   trait_label,
                                                   trait_node_type,
                                                   has_attribute,
                                                   has_attribute_type,
                                                   provided_by])
                        seen_node[trait_uri] += 1
                    #write organism to trait edge
                    if trait_id not in seen_edge:
                        if trait_uri in skip:
                            continue
                        trait_curie = eol_trait_ids[trait_uri]['curie']
                        value = row['value_uri']
                        if value != '':
                            try:
                                has_attribute_type = eol_trait_ids[value]['curie']
                            except KeyError:
                                print('need to add new value to dictionary 5')
                                print(row)
                            has_quantitative_value = ''
                            has_unit = ''
                        else:
                            has_quantitative_value = row['normal_measurement']
                            has_unit = row['normal_units']
                            if has_unit == '':
                                has_unit = row['normal_units_uri']
                            if has_quantitative_value == '':
                                has_quantitative_value = row['measurement']
                                has_unit = row['units']
                                if has_unit == '':
                                    has_unit = row['units_uri']
                            try:
                                has_unit = eol_trait_ids[has_unit]['label']
                            except KeyError:
                                if has_unit != '':
                                    print('need to add a unit to the dictionary 6')
                        write_node_edge_item(fh=edge,
                                             header=self.edge_header,
                                             data=[org_id,
                                                   org_to_trait_edge_label,
                                                   trait_curie,
                                                   org_to_trait_edge_relation,
                                                   trait_label,
                                                   has_attribute_type,
                                                   has_quantitative_value,
                                                   has_unit,
                                                   has_qualitative_value,
                                                   provided_by])
                        seen_node[trait_id] += 1
        #place the EOL trait IDs in context
            with open(os.path.join(self.input_base_dir, 'EOL_ontology.txt'), 'r') as f:
                for line in f:
                    line = line.strip()
                    row = line.split('\t')
                    parent = row[0]
                    child = row[1]
                    has_attribute = ''
                    has_attribute_type = ''
                    has_quantitative_value = ''
                    has_unit = ''
                    has_qualitative_value = ''
                    provided_by = ''
                    label = ''
                    if parent not in seen_node:
                        write_node_edge_item(fh=node,
                                             header=self.node_header,
                                             data=[parent,
                                                   label,
                                                   trait_node_type,
                                                   has_attribute,
                                                   has_attribute_type,
                                                   provided_by])
                        seen_node[parent] += 1
                    if child not in seen_node:
                        write_node_edge_item(fh=node,
                                             header=self.node_header,
                                             data=[child,
                                                   label,
                                                   trait_node_type,
                                                   has_attribute,
                                                   has_attribute_type,
                                                   provided_by])
                        seen_node[parent] += 1
                    write_node_edge_item(fh=edge,
                                         header=self.edge_header,
                                         data=[parent,
                                               org_to_parent_edge_label,
                                               child,
                                               org_to_parent_edge_relation,
                                               has_attribute,
                                               has_attribute_type,
                                               has_quantitative_value,
                                               has_unit,
                                               has_qualitative_value,
                                               provided_by])

"""
Worry about location and habitat nodes later
                        elif trait_uri in location_uris:
                            #print('location trait')
                            trait_uri = row['value_uri']
                            #print(trait_uri)
                            if trait_uri == '':
                                try:
                                    trait_uri = trait_labels[row['literal']]['uri']
                                    #print(trait_uri)
                                except KeyError:
                                    if 'Pacific Basin excluding Hawaii' in row['literal']:
                                        continue
                                    else:
                                        print(row)
                                        print('error a')
                                trait_label = row['literal']
                                #print(trait_label)
                                try:
                                    trait_curie = eol_trait_ids[trait_uri]['curie']
                                except KeyError:
                                    print('need to add a trait to the dictionary 1')
                                    print(row)
                            else:
                                try:
                                    trait_label = eol_trait_ids[trait_uri]['label']
                                    trait_curie = eol_trait_ids[trait_uri]['curie']
                                except KeyError:
                                    if 'mrgid' in trait_uri:
                                        continue
                                    else:
                                        print('need to add a trait to the dictionary 2')
                                        print(row)
                            #write location node
                            if trait_uri not in seen_node:
                                has_attribute = ''
                                has_attribute_type = ''
                                write_node_edge_item(fh=node,
                                                     header=self.node_header,
                                                     data=[trait_curie,
                                                           trait_label,
                                                           env_node_type,
                                                           has_attribute,
                                                           has_attribute_type,
                                                           provided_by])
                                seen_node[trait_uri] += 1
                    #write organism to location edge
                    if trait_id not in seen_edge:
                        has_quantitative_value = ''
                        has_unit = ''
                        has_qualitative_value = ''
                        write_node_edge_item(fh=edge,
                                             header=self.edge_header,
                                             data=[org_id,
                                                   org_to_env_edge_label,
                                                   trait_uri,
                                                   org_to_env_edge_relation,
                                                   trait_label,
                                                   has_attribute_type,
                                                   has_quantitative_value,
                                                   has_unit,
                                                   has_qualitative_value,
                                                   provided_by])
                        seen_node[trait_id] += 1
"""
            # Files write ends