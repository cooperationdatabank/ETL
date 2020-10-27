from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, XSD, OWL
import pandas as pd
import os,sys,string
import requests

coda_vocab = Namespace("https://data.cooperationdatabank.org/vocab/")
coda_res = Namespace("https://data.cooperationdatabank.org/id/")
resourceDir = os.getenv('TRIPLY__PATHS__DATA_DIR', ".")


"""
utility fcts
"""
def isEmpty(val):
    emptyVals =[ "", "NA", "NaN" , "N/A" , 'nan' , 'None' , '999' ,'999.0',  'missing' , 'other' , 'others', 'Other', 'Others']
    if str(val) in emptyVals : return True
    return False



def parse(s):
    clean = ""
    for char in s:
        if char in string.punctuation or char == " " :
            clean = clean+'-'
        else :
            clean = clean+char
    return clean


def readCSV(inFile):
    """
    returns csv without headers
    """
    df  = pd.read_csv(inFile,  na_filter = False, header=0, encoding="latin-1" )
    return df


def save_graph(graph, output_name):
    graph.serialize(destination="%s" % output_name, format='trig')


def add_wikidata_info(countries,indicators):
    wikidataQ = """ 
    SELECT DISTINCT * WHERE 
        { ?s ?p ?o. 
          ?s wdt:P984 ?name.
          VALUES ?name { ::slist:: } 
          VALUES ?p { ::plist:: }. 
      }
    """
    wikidataEP = "https://query.wikidata.org/sparql"
    
    wprops = " ".join(i for i in indicators)
    val_countries = " ".join('"%s"' % j for j in countries)
    
    query  = wikidataQ.replace("::slist::",val_countries).replace("::plist::", wprops)
    
    try:
        resp = requests.get(wikidataEP, params={'query': query, 'format': 'json'}).json()
    except requests.exceptions.RequestException as e:
        print("RequestException for Wikidata %s" % str(e) )
        resp = []
    
    return resp

def add_fb_info(countries, indicators):
    fbQuery = """
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    SELECT ?valueName ?p ?o ?name WHERE {
    service <https://query.wikidata.org/sparql> {
        ?s wdt:P984 ?name.
    	?s wdt:P297 ?value.
          BIND (IRI(concat("http://www.daml.org/2001/09/countries/fips#",?value) ) as ?valueName)
        } 
    	?valueName ?p ?o    
      values ?p { ::flist:: }
      values ?name { ::nlist:: }
    }
    
    """
    
    fbEndpoint = "https://api.triplydb.com/datasets/rvo/landen-portaal/services/landen-portaal/sparql"
    
    fblist = " ".join("<%s>" % i for i in indicators)
    val_countries = " ".join('"%s"' % j for j in countries)
    
    query = fbQuery.replace("::flist::", fblist).replace("::nlist::", val_countries)
    
    try:
        resp = requests.get(fbEndpoint, params={'query': query, 'format': 'json' }).json() ## canot make , 'Content-Type':'application/json' work
    except requests.exceptions.RequestException as e:
        print("RequestException for Factbook %s" % str(e) )
        resp = []
    
    return resp

if __name__ == "__main__":
    print('######\n Converting country indicators ...')
    
    vocab = readCSV(resourceDir + "/input/indicators-vocab.csv")

    indicators = list()
    wd_indicators = list()
    fb_indicators = list()
    
    v = Graph(identifier=Namespace("https://data.cooperationdatabank.org/countryVocab"))
    v.namespace_manager.bind("cd", Namespace("https://data.cooperationdatabank.org/"))
    v.namespace_manager.bind("dct", Namespace("http://purl.org/dc/terms/"))
    
    for ix, construct in vocab.iterrows():
        if 'N' in construct['keep (Y/N)']: continue

        indicator = URIRef(construct['p'])
        v.add((indicator ,RDF.type, RDF.Property))
        if construct['new label'] != '':
            v.add(( indicator , RDFS.label, Literal(construct['new label'],datatype=XSD.string) ))
        elif construct['pAltName'] != '':
            v.add(( indicator , RDFS.label, Literal(construct['pAltName'],datatype=XSD.string) ))
        else :
            v.add(( indicator , RDFS.label, Literal(construct['pLabel'],datatype=XSD.string) ))
        if construct['definition'] != '':
            v.add(( indicator, URIRef("http://purl.org/dc/terms/description"), Literal(construct['definition'], datatype=XSD.string ) ))
        if construct['p'] not in indicators :
            
            ## add to wikidata list
            if construct['gLabel'] == 'wikidata' :
                wd_indicators.append("wdt:%s" % construct['pLabel'])
            if construct['gLabel'] == 'factbook' :
                fb_indicators.append("%s" % construct['p'])
                
            indicators.append(construct['pLabel'])

    print("Country vocab graph has %d triples" % len(v))
    save_graph(v,resourceDir+ "/output_graphs/indicator-vocab.n3")
    
    #### now onto instances
    
    g = Graph(identifier=Namespace("https://data.cooperationdatabank.org/countryIndicators"))
    g.namespace_manager.bind("cd", Namespace("https://data.cooperationdatabank.org/"))
    g.namespace_manager.bind("wdt", Namespace("http://www.wikidata.org/prop/direct/"))
    g.namespace_manager.bind("cdc", Namespace("https://data.cooperationdatabank.org/vocab/"))
    g.namespace_manager.bind("cdp", Namespace("https://data.cooperationdatabank.org/vocab/prop/"))
    g.namespace_manager.bind("fb", Namespace("http://www.daml.org/2001/12/factbook/factbook-ont#"))
    
    country_data = readCSV(resourceDir + "/input/indicators_reversed_all_zscored_coda_2.1.csv")
    
    seen = list()
    
    for ix,country_row in country_data.iterrows() :
        
        country_res =  URIRef(coda_res+"country/"+country_row['code_coda'])

        # this should speed up
        if country_row['code_coda'] not in seen :
            seen.append(country_row['code_coda'])
            
        for indicator,value in country_row['societal_cynicism_zscore':'ESS_avg_importance_loyalty_reversed_zscore'].iteritems():
            if indicator not in indicators : 
                continue
            if not isEmpty(value):

                # storing observations as a BNode for the moment (TODO : qbes )
                # indicators are qb:MeasureProperty
                observation = BNode()

                g.add((observation, RDF.type, coda_vocab.Observation))
                g.add((observation, URIRef(coda_vocab+"prop/value"), Literal(value, datatype=XSD.double ) ))
                g.add((observation, URIRef(coda_vocab+"prop/year"), Literal(country_row['year'], datatype=XSD.gYear ) ))
                g.add((country_res, URIRef(coda_vocab+"prop/"+indicator), observation ))

    
    ### wikidata from https://query.wikidata.org/
    wikiresp = add_wikidata_info(seen,wd_indicators)
    
    for item in wikiresp['results']['bindings']:
        g.add((URIRef("https://data.cooperationdatabank.org/id/country/%s" % item['name']['value']),  URIRef(item['p']['value']), URIRef(item['o']['value']) ))
    
    
    ### factbook from https://triplydb.com/rvo/landen-portaal/sparql/landen-portaal
    factbookresp = add_fb_info(seen,fb_indicators)
 
    for item in factbookresp:  ## NB triply's response is parsed already
       # print(item)
        objectValue = ""  
        if item['o'].startswith('http') : 
            objectValue = URIRef(item['o']) 
        else :
            objectValue = Literal(item['o'])
        g.add((URIRef("https://data.cooperationdatabank.org/id/country/%s" % item['name']), URIRef(item['p']), objectValue ))
    
    print("Country graph has %d triples" % len(g))
    
    save_graph(g,"./graph_temp.n3")
    os.system("sed 's/\-[0-9][0-9]\-[0-9][0-9]\"\^\^xsd:gYear/\"\^\^xsd:gYear/g' graph_temp.n3 >| "+resourceDir+"/output_graphs/country-indicators.n3   ")
    os.remove("graph_temp.n3")
