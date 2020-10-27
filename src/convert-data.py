from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, XSD, SKOS, OWL
from rdflib.collection import Collection
from rdflib.term import _is_valid_uri
import string
import os,sys
from xml.sax._exceptions import SAXParseException
from rdflib.plugins.parsers.ntriples import ParseError
import pandas as pd
from tqdm import tqdm



# dct = Namespace("http://purl.org/dc/terms/")
# coda_res = Namespace("https://coda.triply.cc/"+ os.getenv('ETL_API_ACCOUNT_NAME', "coda-dev")+"/databank/id/")
# coda_vocab = Namespace("https://coda.triply.cc/"+ os.getenv('ETL_API_ACCOUNT_NAME', "coda-dev")+"/vocab/")
# CODA = Namespace("https://coda.triply.cc/" + os.getenv('ETL_API_ACCOUNT_NAME', "coda-dev")+"/"+os.getenv('ETL_DATASET_NAME', "databank")+"/")
resourceDir = os.getenv('TRIPLY__PATHS__DATA_DIR', ".")


dct = Namespace("http://purl.org/dc/terms/")
coda_class = Namespace("https://data.cooperationdatabank.org/vocab/class/")
coda_prop = Namespace("https://data.cooperationdatabank.org/vocab/prop/")
CODA = Namespace("https://data.cooperationdatabank.org/")

"""
utility fcts
"""
def isEmpty(val):
    emptyVals =[ "", "na ", "na" ,'n/a',"nan" , 'none' , '999' ,'999.0', '-999' ,'-999.0', "#REF!" , '#DIV/0!','missing']
    if str(val).lower() in emptyVals : return True
    return False


def parse(s):
    # print(s)
    invalid_uri_chars = '<>" {}|\\^`'
    clean = ""
    if s[-1] == " ": s = s[:-1]
    for char in s:
        if char in invalid_uri_chars :
            clean = clean+'_'
        else :
            clean = clean+char
    # if not _is_valid_uri(clean) :
  #       input(clean)
    return clean

def fill(dataframe, colname):
    last_value = ""

    for index,value in dataframe[colname].iteritems():
        if value == '' :
            dataframe.loc[index,colname] = last_value
        else :
            last_value = value
    return dataframe

def cleanName(vocab, isClass ):
    if vocab[:3] == 'has' :
        if isClass == True: return vocab[3:][0].upper()+vocab[3:][1:]
        else : return vocab[3:][0].lower()+vocab[3:][1:]
    elif vocab[:2] == 'is':
        if isClass == True: return vocab[2:][0].upper()+vocab[2:][1:]
        else : return vocab[2:][0].lower()+vocab[2:][1:]
    else :
        if isClass == True: return vocab[0].upper()+vocab[1:]
        else : return vocab[0].lower()+vocab[1:]

def readCSV(inFile, h_index):
    """
    returns csv without headers
    """
    df  = pd.read_csv(inFile,  na_filter = False, header=h_index, low_memory=False, encoding="latin-1" )
    return df

def read_input_files() :
    """
        read files : effect sizes, treatments, studies, papers, vocabulary
        creates csv tables and stores everything in an obj
    """
    print ('loading data...',end=" ")
    print("1...", end=" ")
    effects_df = readCSV(resourceDir+ '/input/effect_sizes_computed.csv', 0)

    print("2...", end=" ")
    treatments_df = readCSV(resourceDir+ '/input/data_clean.csv', 0) # file has headers on the 2nd row
    treatments_df = treatments_df.rename(columns={'treatment_1':'treatment_ID'})

    print("3...", end=" ")
    study_df = readCSV(resourceDir+ '/input/Study_characteristics.csv', 0)

    print("4...\n", end=" ")
    dois_df = readCSV(resourceDir+ '/input/IDs.csv', 0)

    return {'es' : effects_df, 'trts' : treatments_df, 'studies' : study_df, 'papers' : dois_df }

def save_graph(graph, output_name):

    graph.namespace_manager.bind("cdp", coda_prop)
    graph.namespace_manager.bind("cdc", coda_class)
    graph.namespace_manager.bind("cdr", CODA)
    graph.namespace_manager.bind("dct",dct)
    graph.namespace_manager.bind("skos", SKOS)
    graph.namespace_manager.bind("owl", OWL)

    graph.serialize(destination="%s" % output_name, format='trig')


def fill_vocabulary_file(codebook):
    # import codebook
    codebook_csv =  pd.read_csv(resourceDir+ codebook,keep_default_na = False)
    fill(codebook_csv,'Superclass')
    fill(codebook_csv,'Concept')
    fill(codebook_csv,'Concept Readable Label')
    fill(codebook_csv,'Concept 2.0')

    # save to new file
    codebook_csv.to_csv(resourceDir+ '/input/codebook_clean.csv',index =False)


"""
classes
"""
class StudyBuilder:

    def __init__(self):
        self.study_graph = Graph(identifier=CODA.Studies)

    def replaceMatchingValues(self,current_value):
        """
        Matching ="3" becomes 2
        Matching = "4" becomes 2
        Matching = "4 ; 3" becomes 2
        Matching = "4 ; N/A" becomes 2 ; N/A
        Matching = "1 ; 2 ; 4" becomes 1 ; 2
        Matching = "1 ; 3" becomes 1 ; 2
        Matching = "1 ; 4" becomes 1 ; 2
        Matching = "2 ; 3" becomes 2
        Matching = "2 ; 4" becomes 2
        """
        # print (current_value)
        if current_value == '' : new_value = '999'
        elif current_value[0] == "3" or current_value[0] == "4"  :
            new_value = "2"
        elif current_value[0] == "2" and len(current_value) > 2  :
            new_value = "2"
        elif current_value[0] == "1" and len(current_value) > 2 :
            new_value = "1 ; 2"
        elif current_value[0] == "4 ; N/A" :
            new_value = "2 ; N/A"
        else :
            new_value = current_value

        # print("old :",current_value,"; new :",new_value)
        return new_value

    def replaceRecrMethValues(self,current_value):
        """
        Recr_Meth = "4" becomes 3
        Recr_Meth = "5" becomes 3
        Recr_Meth = "1 ; 4" becomes 1 ; 3
        Recr_Meth = "1 ; 5" becomes 1 ; 3
        Recr_Meth = "2 ; 4" becomes 2 ; 3
        Recr_Meth = "3 ; 4" becomes 3
        Recr_Meth = "3 ; 5" becomes 3
        Recr_Meth = "4 ; 5" becomes 3
        Recr_Meth = "3 ; 5" becomes 3
        """

        # print(current_value)
        if current_value == '' : new_value = '999'
        elif current_value == "4" or current_value == "5"  :
            new_value = "3"
        elif current_value[0] == "3" and len(current_value) > 2  :
            new_value = "3"
        elif current_value[0] == "4" and len(current_value) > 2  :
            new_value = "3"
        elif current_value[0] == "1" and len(current_value) > 2  :
            new_value = "1 ; 3"
        elif current_value[0] == "2" and len(current_value) > 2  :
            new_value = "2 ; 3"
        elif current_value == '4 ; 2': new_value = "2 ; 3"
        else :
            new_value = current_value
        # print(new_value," ",current_value)
        return new_value

    def build_study_info(self, new_study, study_df):
        # new_study : URIRef()
        # study_df : dict

        for col in list(study_df.keys()):


            if vocabMngr.get_column_name(col)  == False and col != 'Country' :
                # print ("skipping %s " % col)
                continue

            ### catch Matching and Recr_meth (need to be changed in values)
            if col == 'Matching' :
                study_df[col] = self.replaceMatchingValues(study_df[col].replace("[","").replace("]","").replace(","," ; "))

            if col == 'Recr_Meth' :
                study_df[col] = self.replaceRecrMethValues(study_df[col].replace("[","").replace("]","").replace(","," ; "))

            # value cleanup
            if col not in ['Comments', 'descriptionIV','Other variables measured'] :
                s_values = str(study_df[col]).replace("[","").replace("]","").replace(","," ; ").split(" ; ")
            else :
                # this should avoid splitting the comment columns
                s_values = [study_df[col]]



            for s_value in s_values:

                if isEmpty(s_value): continue

                s_value = s_value.strip()

                # create the property

                if col in ['Age range, upper limit' , 'Choice range upper'] :
                    continue
                elif col in [ 'Age range, lower limit']:
                    newProp = URIRef(coda_prop.ageRange)
                elif col in [ 'Choice range lower'] :
                    newProp = URIRef(coda_prop.choiceRange)
                elif col == 'Country' :
                    newProp = URIRef(coda_prop.country)
                else:
                    newProp = vocabMngr.get_column_name(col)

                # identify values
                if vocabMngr.get_prop_range(newProp) == XSD.boolean :
                    if s_value == '1' or s_value == 1:
                        self.study_graph.add((new_study, newProp, Literal(True, datatype=XSD.boolean)))
                    elif s_value == '0' or s_value == 0:
                        self.study_graph.add((new_study, newProp, Literal(False, datatype=XSD.boolean)))
                    else :
                        # this should not happen
                        errorSet.add(("Wrong boolean value", new_study, newProp, s_value))
                        print("For study %s, prop <%s> neither T nor F : <%s>, skipping..." % (new_study, newProp, s_value) )

                elif vocabMngr.get_prop_range(newProp) == XSD.double :
                    self.study_graph.add((new_study, newProp, Literal(s_value, datatype=XSD.double ) ))
                elif vocabMngr.get_prop_range(newProp) == XSD.gYear :
                    self.study_graph.add((new_study, newProp, Literal(s_value, datatype=XSD.gYear ) ))
                elif vocabMngr.get_prop_range(newProp) == XSD.integer :
                    self.study_graph.add((new_study, newProp, Literal(s_value, datatype=XSD.integer ) ))
                elif vocabMngr.get_prop_range(newProp) == XSD.string :
                    self.study_graph.add((new_study, newProp, Literal(s_value, datatype=XSD.string ) ))
                elif vocabMngr.get_prop_range(newProp) == coda_class.Country :
                     self.study_graph.add((new_study, newProp, URIRef("%sid/%s/%s" % (CODA , newProp.split("/")[-1].lower(), s_value )) ))
                     vocabMngr.addToCountries(URIRef("%sid/%s/%s" % (CODA , newProp.split("/")[-1].lower(), s_value )))
                elif vocabMngr.get_prop_range(newProp) == coda_class.ValueRange :

                    minval = str(s_value) # it's either choice or age range lower

                    if newProp == URIRef(coda_prop.ageRange):
                        listMaxVal = str(study_df['Age range, upper limit']).split(" ; ")
                    elif newProp == URIRef(coda_prop.choiceRange):
                        listMaxVal = str(study_df['Choice range upper']).split(" ; ")
                    else :
                        print("This should not happen! %s %s " % (newProp, s_value) )
                    for maxval in listMaxVal :
                        if isEmpty(maxval)  : continue
                        valueRange = BNode()
                        self.study_graph.add((valueRange, RDF.type, coda_class.ValueRange))
                        self.study_graph.add((valueRange, coda_prop.lowerInclusive, Literal(minval, datatype= XSD.double )) )
                        self.study_graph.add((valueRange, coda_prop.higherInclusive, Literal(maxval, datatype= XSD.double )) )
                        self.study_graph.add((valueRange, RDFS.label, Literal("[%s,%s]" % (minval, maxval)) ))
                        self.study_graph.add((new_study, newProp, valueRange))
                                #
                else :

                    if not _is_valid_uri("%sid/%s/%s" % (CODA , newProp.split("/")[-1].lower(), parse(s_value).lower() )):
                        print("Wrong URI : %sid/%s/%s" % (CODA , newProp.split("/")[-1].lower(), parse(s_value).lower() ))
                        errorSet.add(("Wrong syntax for value",new_study, newProp, s_value ))

                    instance = URIRef("%sid/%s/%s" % (CODA , newProp.split("/")[-1].lower(), parse(s_value).lower() ))
                    self.study_graph.add((new_study, newProp, instance))

                    if not vocabMngr.term_exists(instance):
                        print("From study : %s , individual <%s> (prop : <%s>) not in vocab. " % ( new_study,   newProp, instance ))
                        errorSet.add(("Missing value in codebook", new_study, newProp, instance))


                if not vocabMngr.term_exists(newProp) and col not in ['Choice range lower', 'Choice range upper','Age range, lower limit', 'Age range, upper limit'] :
                    print(" %s not in vocab. " % ( newProp ))
                    errorSet.add(("Missing property in codebook", new_study, newProp, ""))

        return

    def get_graph(self):
        return self.study_graph

    def add_triple(self,triple):
        self.study_graph.add(triple)

class VocabularyManager:

    def __init__(self, codebook_datafile):

        self.codebook = readCSV(codebook_datafile,0)

        self.vocab_graph = Graph(identifier=CODA.Vocab)

        self.propsToColname = dict()
        self.ontoProps = list()
        self.countryList = list() # exception

        self.__buildBasicClasses()
        self.__create_ontology_vocab()
        self.__create_treatment_vocab()


        print("Vocabulary has %d triples." % len(self.vocab_graph))

        # create a list of subjects
        self.vocab_subjects = list(self.vocab_graph.subjects())

        # store ranges of props
        self.ranges = dict()
        for s in self.vocab_subjects :
            self.ranges[s] = self.vocab_graph.value(s,RDFS.range)

    def addToCountries(self, country):
        if country not in self.countryList:
            self.countryList.append(country)
        return

    def addCountryListToGraph(self):
        bnode = BNode()
        c = Collection( self.vocab_graph , bnode, list(i for i in self.countryList))
        self.vocab_graph.add((coda_class.Country, OWL.oneOf, bnode ))

        for country in self.countryList :
            self.vocab_graph.add( (country,RDF.type,coda_class.Country) )
            self.vocab_graph.add( (country,RDFS.label,Literal(country.split("/")[-1], datatype=XSD.string)))
        return

    def get_graph(self):
        return self.vocab_graph

    def isOntoProp(self,p):
        if p in self.ontoProps : return True
        return False

    def get_column_name(self,p):
        if p in self.propsToColname.keys():
            return self.propsToColname[p]
        return False

    def get_prop_range(self,p):
        return self.ranges[p]

    def term_exists(self,term):
        if term not in self.vocab_subjects:
            return False
        return True

    def __buildBasicClasses(self):

        self.vocab_graph.add((URIRef(coda_class.Study), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.Study), RDFS.label, Literal("Study", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.Study), dct.description, Literal("A sample of observations of a phenomenon in either a contolled (e.g., random assignment) or natural setting.", datatype = XSD.string)))

        ####

        self.vocab_graph.add((URIRef(coda_class.Paper), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.Paper), RDFS.label, Literal("Paper", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.Paper), dct.description, Literal("A document reporting the methods and results of one or more studies.", datatype = XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.study), RDF.type, OWL.ObjectProperty))
        self.vocab_graph.add((URIRef(coda_prop.study), RDFS.label, Literal("includes study", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.study), dct.description, Literal("the methods and results reported in a paper.", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.study), RDFS.domain, URIRef(coda_class.Paper)))
        self.vocab_graph.add((URIRef(coda_prop.study), RDFS.range, URIRef(coda_class.Study)))

        ####

        self.vocab_graph.add((URIRef(coda_class.Country), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.Country), RDFS.label, Literal("Country", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.Country), dct.description, Literal("Country where the data collection took place (coded with the 3-letter country code following ISO 3166-1 alpha-3).", datatype = XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.country), RDF.type, OWL.ObjectProperty))
        self.vocab_graph.add((URIRef(coda_prop.country), RDFS.label, Literal("has country", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.country), dct.description, Literal("Country where the data collection took place. Can overlap with participant's nationality.", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.country), RDFS.domain, URIRef(coda_class.Study)))
        self.vocab_graph.add((URIRef(coda_prop.country), RDFS.range, URIRef(coda_class.Country)))

        ####

        self.vocab_graph.add((URIRef(coda_class.Treatment), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.Treatment), RDFS.label, Literal("Treatment", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.Treatment), dct.description, Literal("Treatments define when observations of a phenomenon occur in different contexts, such as multiple levels of a manipulated independent variable.", datatype = XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.treatment), RDF.type, OWL.ObjectProperty))
        self.vocab_graph.add((URIRef(coda_prop.treatment), RDFS.label, Literal("compares treatment", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.treatment), dct.description, Literal("the treatments compared in the effect size.", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.treatment), RDFS.domain, URIRef(coda_class.Observation)))
        self.vocab_graph.add((URIRef(coda_prop.treatment), RDFS.range, URIRef(coda_class.Treatment)))

        ####
        self.vocab_graph.add((URIRef(coda_class.Observation), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.Observation), RDFS.label, Literal("Observation", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.Observation), dct.description, Literal("An association between a continuous independent variable and an outcome variable, or a contrast between two levels of a categorical independent variable on an outcome variable.", datatype = XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.reportsEffect), RDF.type, OWL.ObjectProperty))
        self.vocab_graph.add((URIRef(coda_prop.reportsEffect), RDFS.label, Literal("reports effect size", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.reportsEffect), dct.description, Literal("The effect size reported in a study.", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.reportsEffect), RDFS.domain, URIRef(coda_class.Study)))
        self.vocab_graph.add((URIRef(coda_prop.reportsEffect), RDFS.range, URIRef(coda_class.Observation)))

        ########

        self.vocab_graph.add((URIRef(coda_class.IndependentVariable), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.IndependentVariable), RDFS.label, Literal("IndependentVariable", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.IndependentVariable), dct.description, Literal("A variable that is measured or manipulated and than related to a dependent variable, such as cooperation.", datatype = XSD.string)))

        ####

        self.vocab_graph.add((URIRef(coda_class.DOI), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.DOI), RDFS.label, Literal("DOI", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.DOI), dct.description, Literal("Digital Object Identifier that is a string of numbers, letters, and symbols that can be used to identify a document and link to it on the web.", datatype = XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.doi), RDF.type, OWL.ObjectProperty))
        self.vocab_graph.add((URIRef(coda_prop.doi), RDFS.label, Literal("has DOI", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.doi), dct.description, Literal("The Digital Object Identifier of the paper.", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.doi), RDFS.domain, URIRef(coda_class.Paper)))
        self.vocab_graph.add((URIRef(coda_prop.doi), RDFS.range, URIRef(coda_class.DOI)))

        return

    def __create_ontology_vocab(self ):
        oneOfDict = dict()

        for ix, vocab_row in self.codebook.iterrows():

            if vocab_row['Codebook'] != 'Ontology': continue

            # name cleaning
            class_name = cleanName(vocab_row['Concept'], True)
            prop_name = cleanName(vocab_row['Concept'], False)

            newProp = URIRef(coda_prop[parse(prop_name)])
            newSuperProp = URIRef(coda_prop[parse(vocab_row['Superclass']+"Variable")])
            self.vocab_graph.add((newSuperProp, RDF.type, RDF.Property))
            self.vocab_graph.add((newSuperProp, RDFS.label, Literal(vocab_row['Superclass']+"-related independent variables", datatype = XSD.string )))
            self.vocab_graph.add((newProp, RDFS.subPropertyOf, newSuperProp))

            self.propsToColname[vocab_row['Concept']] = newProp
            self.ontoProps.append(newProp)

            # prop
            if vocab_row['Values'] == '[double]' :
                self.vocab_graph.add((newProp, RDF.type, OWL.DatatypeProperty))
                self.vocab_graph.add((newProp, RDFS.range, XSD.double))
            elif vocab_row['Values'] == '[int]' :
                self.vocab_graph.add((newProp, RDF.type, OWL.DatatypeProperty))
                self.vocab_graph.add((newProp, RDFS.range, XSD.integer))
            elif vocab_row['Values'] == '[string]':
                self.vocab_graph.add((newProp, RDF.type, OWL.DatatypeProperty))
                self.vocab_graph.add((newProp, RDFS.range, XSD.string))
            elif vocab_row['Values'] == '[bool]':
                self.vocab_graph.add((newProp, RDF.type, OWL.DatatypeProperty))
                self.vocab_graph.add((newProp, RDFS.range, XSD.boolean))
                self.vocab_graph.add((newProp, RDFS.label, Literal(vocab_row['Concept Readable Label'], datatype = XSD.string)))
            else:

                # then it's an object prop
                self.vocab_graph.add((newProp, RDF.type, OWL.ObjectProperty))

                # and we need a new class and its superclass
                newClass = URIRef(coda_class[parse(class_name)])

                if newClass not in oneOfDict.keys() : oneOfDict[newClass] = list()

                superclass = URIRef(coda_class[parse(vocab_row['Superclass']+"Variable")])

                # superclass
                self.vocab_graph.add((superclass, RDF.type, OWL.Class))
                self.vocab_graph.add((superclass, RDFS.subClassOf, URIRef(coda_class.IndependentVariable)))
                self.vocab_graph.add((superclass, RDFS.label, Literal(vocab_row['Superclass']+"-related independent variables", datatype = XSD.string )))

                # class
                self.vocab_graph.add((newClass, RDFS.subClassOf, superclass))
                self.vocab_graph.add((newClass, RDF.type, OWL.Class))

                # definitions
                if vocab_row['Concept Definition'] != "":
                    self.vocab_graph.add((newClass, dct.description, Literal(vocab_row['Concept Definition'], datatype = XSD.string)))
                if vocab_row['Concept Readable Label'] != "" :
                    self.vocab_graph.add((newClass, RDFS.label, Literal(vocab_row['Concept Readable Label'], datatype = XSD.string)))
                if vocab_row['Concept Synonym'] != "":
                    self.vocab_graph.add((newClass, SKOS.altLabel, Literal(vocab_row['Concept Synonym'], datatype = XSD.string)))
                if vocab_row['Superclass Definition'] != "":
                    self.vocab_graph.add((superclass, dct.description, Literal(vocab_row['Superclass Definition'], datatype = XSD.string)))

                self.vocab_graph.add((newProp, RDFS.range, newClass))
                self.vocab_graph.add((newProp, RDFS.label, Literal(vocab_row['Concept Readable Label'], datatype = XSD.string)))

                # individuals
                ###

                instance = URIRef("%sid/%s/%s" % (CODA , parse(newProp.split("/")[-1]).lower(), parse(vocab_row['Values'].lower())) )

                self.vocab_graph.add((instance, RDFS.label, Literal(vocab_row['Values'],datatype=XSD.string )))
                oneOfDict[newClass].append(instance)

                self.vocab_graph.add((instance, RDF.type, newClass))
                self.vocab_graph.add((instance, dct.description, Literal(vocab_row['Values Definition'],datatype=XSD.string)))


            # finally give it a name and a range
            self.vocab_graph.add((newProp, RDFS.domain, URIRef(coda_class.Treatment)))

            if  vocab_row['Values Synonyms'] != "" :
                self.vocab_graph.add((instance,  SKOS.altLabel, Literal(vocab_row['Values Synonyms'], datatype = XSD.string)))
            if vocab_row['Concept Readable Label'] != "":
                self.vocab_graph.add((newProp, RDFS.label,  Literal(vocab_row['Concept Readable Label'], datatype = XSD.string)))
            if vocab_row['Concept Definition'] != "":
                self.vocab_graph.add((newProp, dct.description, Literal(vocab_row['Concept Definition'], datatype = XSD.string)))
            if vocab_row['Concept Synonym'] != "":
                self.vocab_graph.add((newProp,  SKOS.altLabel, Literal(vocab_row['Concept Synonym'], datatype = XSD.string)))
            if vocab_row['Concept Mapping'] != "" :
                for term in vocab_row['Concept Mapping'].split(" ; "):
                    if "?term=" in term : continue
                    if term[0] == "*":
                        self.vocab_graph.add((instance, SKOS.relatedMatch, URIRef(term[1:])))
                    else:
                        self.vocab_graph.add((instance, SKOS.exactMatch, URIRef(term)))
            if vocab_row['Value Mapping'] != "":
                for term in vocab_row['Value Mapping'].split(" ; "):
                    # TODO : that's temp.
                    if "?term=" in term : continue
                    if "*" in term:
                        self.vocab_graph.add((instance, SKOS.relatedMatch, URIRef(term[1:])))
                    else:
                        self.vocab_graph.add((instance, SKOS.exactMatch, URIRef(term)))


        self.vocab_graph.add((URIRef(coda_class.IndependentVariable), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.IndependentVariable), RDFS.label, Literal( "Independent Variable", datatype = XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.IndependentVariable), dct.description,Literal( "Variable manipulated by an experimenter.", datatype = XSD.string) ))

        ## add class enumerations
        for ontoClass in oneOfDict.keys() :
            bnode = BNode()
            c = Collection( self.vocab_graph , bnode, list(i for i in oneOfDict[ontoClass] ))
            self.vocab_graph.add((ontoClass, OWL.oneOf, bnode ))



    def __create_treatment_vocab(self) :
        oneOfDict2 = dict()

        for ix, vocab_row in self.codebook.iterrows():

            if vocab_row['Codebook'] == 'Ontology' or vocab_row['Codebook'] == 'Default': continue

            # exceptions
            if vocab_row['Concept'] in ['Country','Age range, upper limit', 'Age range, lower limit','Choice range lower','Choice range upper'] :
                if vocab_row['Concept'][0:3] == 'Age' :
                    self.propsToColname[vocab_row['Concept']] = URIRef(coda_prop.ageRange)
                else:
                    self.propsToColname[vocab_row['Concept']] = URIRef(coda_prop.choiceRange)
                continue

            # name cleaning
            prop_name = cleanName(vocab_row['Concept 2.0'], False)

            newProp = URIRef(coda_prop[parse(prop_name)])
            self.propsToColname[vocab_row['Concept']] = newProp

            # prop
            if vocab_row['Values'] == '[double]'  :
                self.vocab_graph.add((newProp, RDF.type, OWL.DatatypeProperty))
                self.vocab_graph.add((newProp, RDFS.range, XSD.double))

            elif vocab_row['Values'] == '[int]' :
                self.vocab_graph.add((newProp, RDF.type, OWL.DatatypeProperty))
                if vocab_row['Concept'] == 'Year of data collection' :
                    self.vocab_graph.add((newProp, RDFS.range, XSD.gYear))
                else :
                    self.vocab_graph.add((newProp, RDFS.range, XSD.integer))

            elif vocab_row['Values'] == '[string]':
                self.vocab_graph.add((newProp, RDF.type, OWL.DatatypeProperty))
                self.vocab_graph.add((newProp, RDFS.range, XSD.string))

            elif vocab_row['Values'] == '[bool]':
                self.vocab_graph.add((newProp, RDF.type, OWL.DatatypeProperty))
                self.vocab_graph.add((newProp, RDFS.range, XSD.boolean))
                self.vocab_graph.add((newProp, RDFS.label, Literal(vocab_row['Concept Readable Label'], datatype = XSD.string)))

            else:
                # then it's an object prop
                self.vocab_graph.add((newProp, RDF.type, OWL.ObjectProperty))

                # and we need a new class
                class_name = parse(cleanName(vocab_row['Concept 2.0'], True))
                newClass = URIRef(coda_class[parse(class_name)])

                self.vocab_graph.add((newClass, RDF.type, OWL.Class))

                # add to enumeration
                if newClass not in oneOfDict2.keys() : oneOfDict2[newClass] = list()

                # definitions
                if vocab_row['Concept Definition'] != "":
                    self.vocab_graph.add((newClass, dct.description, Literal(vocab_row['Concept Definition'], datatype = XSD.string)))
                if vocab_row['Concept Readable Label'] != "" :
                    self.vocab_graph.add((newClass, RDFS.label, Literal(vocab_row['Concept Readable Label'], datatype = XSD.string)))
                if vocab_row['Concept Synonym'] != "":
                    self.vocab_graph.add((newClass, SKOS.altLabel, Literal(vocab_row['Concept Synonym'], datatype = XSD.string)))

                self.vocab_graph.add((newProp, RDFS.range, newClass))
                self.vocab_graph.add((newProp, RDFS.label, Literal(vocab_row['Concept Readable Label'], datatype = XSD.string)))

                # individuals

                # TODO : to be improved
                if vocab_row['Concept 2.0'] == 'StudyCountry' :
                    self.vocab_graph.add((newProp, RDFS.domain, URIRef(coda_class.Study)) )
                    continue


                instance = URIRef("%sid/%s/%s" % (CODA , newProp.split("/")[-1].lower(),parse(vocab_row['Values'].lower()) ))
                self.vocab_graph.add((instance, RDF.type, newClass))
                self.vocab_graph.add((instance, dct.description, Literal(vocab_row['Values Definition'],datatype=XSD.string)))

                if vocab_row['Values readable labels'] != "":
                    self.vocab_graph.add((instance, RDFS.label, Literal(vocab_row['Values readable labels'],datatype=XSD.string)))

                else:
                    self.vocab_graph.add((instance, RDFS.label, Literal(vocab_row['Values'],datatype=XSD.string)))

                oneOfDict2[newClass].append(instance)

                if vocab_row['Values Synonyms'] != "" :
                    self.vocab_graph.add((instance,  SKOS.altLabel, Literal(vocab_row['Values Synonyms'], datatype = XSD.string)))

            # finally give the prop a domain and defs

            if vocab_row['Codebook'] == 'Treatments':
                self.vocab_graph.add((newProp, RDFS.domain, URIRef(coda_class.Treatment)))
            elif vocab_row['Codebook'] == 'EffectSize':
                self.vocab_graph.add((newProp, RDFS.domain, URIRef(coda_class.Observation)))
            else :
                self.vocab_graph.add((newProp, RDFS.domain, URIRef(coda_class.Study)))


            if vocab_row['Concept Readable Label'] != "":
                self.vocab_graph.add((newProp, RDFS.label,  Literal(vocab_row['Concept Readable Label'], datatype = XSD.string)))
            if vocab_row['Concept Definition'] != "":
                self.vocab_graph.add((newProp, dct.description, Literal(vocab_row['Concept Definition'], datatype = XSD.string)))
            if vocab_row['Concept Synonym'] != "":
                self.vocab_graph.add((newProp,  SKOS.altLabel, Literal(vocab_row['Concept Synonym'], datatype = XSD.string)))

        ### additionally add specific classes
        for p in ['higherInclusive', 'lowerInclusive', 'ageRange', 'choiceRange']:
            self.vocab_graph.add((URIRef(coda_prop[p]),RDF.type, OWL.DatatypeProperty))
            if p in ['higherInclusive', 'lowerInclusive']:
                self.vocab_graph.add((URIRef(coda_prop[p]),RDFS.range, XSD.double))
            else :
                self.vocab_graph.add((URIRef(coda_prop[p]),RDFS.range, URIRef(coda_class.ValueRange)))
                self.vocab_graph.add((URIRef(coda_prop[p]),RDFS.domain, coda_class.Study))

        self.vocab_graph.add((URIRef(coda_class.ValueRange), RDF.type, OWL.Class))
        self.vocab_graph.add((URIRef(coda_class.ValueRange), RDFS.label, Literal("Range of values",datatype=XSD.string)))
        self.vocab_graph.add((URIRef(coda_class.ValueRange), dct.description, Literal("Range of 2 values (min inclusive, max inclusive).",datatype=XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.higherInclusive), RDFS.label, Literal("higher value inclusive",datatype=XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.higherInclusive), dct.description, Literal("Higher inclusive value of a range of 2 values.",datatype=XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.lowerInclusive), RDFS.label, Literal("lower value inclusive",datatype=XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.lowerInclusive), dct.description, Literal("Lower inclusive value of a range of 2 values.",datatype=XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.ageRange), RDFS.label, Literal("age range",datatype=XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.ageRange), dct.description, Literal("Range of minimum and maximum age of all sampled participants.",datatype=XSD.string)))

        self.vocab_graph.add((URIRef(coda_prop.choiceRange), RDFS.label, Literal("choice option range",datatype=XSD.string)))
        self.vocab_graph.add((URIRef(coda_prop.choiceRange), dct.description, Literal("The value of the highest and lowest choice option allowed to participants. '0' and '1' indicate a binary choice between non-numeric options (such as 'cooperate' vs. 'defect'; 'C' vs. 'D').",datatype=XSD.string)))


        ## add class enumerations
        for ontoClass in oneOfDict2.keys() :
            bnode = BNode()
            c = Collection( self.vocab_graph, bnode, list(i for i in set(oneOfDict2[ontoClass] )))
            self.vocab_graph.add((ontoClass, OWL.oneOf, bnode ))


class EffectBuilder:

    def __init__(self):
        self.effect_graph = Graph(identifier=CODA.Effects)

    def get_graph(self):
        return self.effect_graph

    def build_effect(self,effect_row):

        if ".NA" in effect_row['effect_ID']: # should not happen
            new_effect = URIRef(CODA['id/']+effect_row['effect_ID'].replace("NA","0"))
        else :
            new_effect = URIRef(CODA['id/']+effect_row['effect_ID'])

        self.effect_graph.add((new_effect, RDF.type, coda_class.Observation))
        self.effect_graph.add((new_effect, RDFS.label, Literal("Effect size no. %s " % effect_row['effect_ID'], datatype=XSD.string)) )

        self.effect_graph.add((URIRef(CODA['id/']+effect_row['study_ID']), coda_prop.reportsEffect, new_effect))
        # input(effect_row['study_ID'])

        for col,es_values in effect_row['DV_behavior':'effectSizeAlgorithm'].iteritems():

            for es_value in es_values.split(" ; "):

                # skip if empty val
                if  isEmpty(es_value): continue

                if vocabMngr.get_column_name(col) == False :
                    # print ("skipping %s " % col)
                    continue
                newProp = vocabMngr.get_column_name(col)


                # add to missing defs if needed
                if not vocabMngr.term_exists(newProp):
                    errorSet.add(("Missing property in codebook",new_effect, newProp, ""))
                else:

                    if vocabMngr.get_prop_range(newProp) == XSD.boolean :
                        if es_value == '1' or es_value == 1:
                            self.effect_graph.add((new_effect, newProp, Literal(True, datatype=XSD.boolean)))
                        elif es_value == '0' or tr_value == 0:
                            self.effect_graph.add((new_effect, newProp, Literal(False, datatype=XSD.boolean)))
                        else :
                            # this should not happen
                            errorSet.add(("Wrong boolean value" ,new_effect, newProp, es_value))
                            continue
                    elif vocabMngr.get_prop_range(newProp) == XSD.double :
                        self.effect_graph.add((new_effect, newProp, Literal(es_value, datatype=XSD.double ) ))
                    elif vocabMngr.get_prop_range(newProp) == XSD.integer :
                        self.effect_graph.add((new_effect, newProp, Literal(es_value, datatype=XSD.integer ) ))
                    elif vocabMngr.get_prop_range(newProp) == XSD.string :
                        self.effect_graph.add((new_effect, newProp, Literal(es_value, datatype=XSD.string ) ))

                    else :

                       if not _is_valid_uri( "%sid/%s/%s" % (CODA , newProp.split("/")[-1].lower(), parse(es_value).lower() ) ):
                           print("Wrong URI : %sid/%s/%s" % ( CODA , newProp.split("/")[-1].lower(), parse(es_value).lower() ) )
                           errorSet.add(("Wrong syntax for value",new_effect, newProp, es_value ))

                       individual = URIRef("%sid/%s/%s" % (CODA , newProp.split("/")[-1].lower(), parse(es_value).lower() ) )
                       self.effect_graph.add((new_effect, newProp,  individual ))

                       if not vocabMngr.term_exists(individual):
                           print("for <%s>  prop <%s> : <%s> not in vocab " % (new_effect, newProp, individual))
                           errorSet.add(("Missing value in codebook",new_effect, newProp, individual ))

            # compares treatments
            t1 = URIRef(CODA['id/']+effect_row['treatment_1'])
            self.effect_graph.add((new_effect, coda_prop.treatment, t1))

            # effects can compare 2 treatments, or measure 1 only. If 1 only, skip col T2
            if not isEmpty(effect_row['treatment_2']):
                t2 = URIRef(CODA['id/']+effect_row['treatment_2'])
                self.effect_graph.add((new_effect, coda_prop.treatment, t2))



class TreatmentBuilder:

    def __init__(self, ):
        self.__treatment_graph__ = Graph(identifier=CODA.Treatments)

    def get_graph(self):
        return self.__treatment_graph__

    def build_treatment(self, treatment_row):

        # treatment
        new_treatment = URIRef(CODA+"id/"+treatment_row['treatment_ID'])
        self.__treatment_graph__.add((new_treatment, RDF.type, coda_class.Treatment))
        self.__treatment_graph__.add((new_treatment, RDFS.label, Literal("Treatment %s" % treatment_row['treatment_ID'])))

        # iterate over IVs columns
        for col,tr_values in treatment_row['BS/WS':'hasMonitoringCost'].iteritems():

            if vocabMngr.get_column_name(col) == False  :
                # print ("skipping %s " % col)
                continue

            # handle column name exceptions
            if col[0:3] == 'has' : colname = col[3:]
            if col[0:2] == 'is' : colname = col[2:]
            else : colname = col


            # iterating over cells if there's multiple values
            # for tr_value in str(tr_values).replace("[","").replace("]","").replace(","," ; ").split(" ; "):
            for tr_value in str(tr_values).replace("[","").replace("]","").split(" ; "):

                if isEmpty(tr_value): continue

                # remove final \s , if any
                tr_value = tr_value.strip()

                newProp = vocabMngr.get_column_name(col)

                if not vocabMngr.term_exists(newProp):
                    errorSet.add(("Missing property in codebook",new_treatment, newProp, ""))
                else:
                    if vocabMngr.get_prop_range(newProp) == XSD.boolean :
                        if tr_value == '1' or tr_value == 1:
                            self.__treatment_graph__.add((new_treatment, newProp, Literal(True, datatype=XSD.boolean)))
                        elif tr_value == '0' or tr_value == 0:
                            self.__treatment_graph__.add((new_treatment, newProp, Literal(False, datatype=XSD.boolean)))
                        else :
                            # this should not happen
                            errorSet.add(("Wrong boolean value",new_treatment, newProp, tr_value))
                            continue
                    elif vocabMngr.get_prop_range(newProp) == XSD.double :
                        self.__treatment_graph__.add((new_treatment, newProp, Literal(tr_value, datatype=XSD.double ) ))
                    elif vocabMngr.get_prop_range(newProp) == XSD.integer :
                        self.__treatment_graph__.add((new_treatment, newProp, Literal(tr_value, datatype=XSD.integer ) ))
                    elif vocabMngr.get_prop_range(newProp) == XSD.string :
                        self.__treatment_graph__.add((new_treatment, newProp, Literal(tr_value, datatype=XSD.string ) ))

                    else :

                        if not _is_valid_uri("%sid/%s/%s" % ( CODA , newProp.split("/")[-1].lower(), parse(tr_value).lower() ) ):
                            print("Wrong URI : %sid/%s/%s" % ( CODA , newProp.split("/")[-1].lower(), parse(tr_value).lower() ) )
                            errorSet.add(("Wrong syntax for value",new_treatment, newProp, tr_value ))

                        individual = URIRef( "%sid/%s/%s" % ( CODA , newProp.split("/")[-1].lower(), parse(tr_value).lower() ))
                        self.__treatment_graph__.add((new_treatment, newProp,  individual ))

                        if not vocabMngr.term_exists(individual):
                            print("for tr : <%s> and prop : <%s> , <%s> not in vocab" % (new_treatment, newProp, individual))
                            errorSet.add(("Missing value in codebook",new_treatment, newProp, individual ))
        return

"""
input files :
    - effect sizes
    - ontology-annotated treatments
    - vocabulary
    - study characteristics
    - paper metadata
output KGs :
    - vocabulary
    - treatments
    - studies
    - dois
    - effect sizes (observations)
"""
if __name__ == "__main__":


    if "output_graphs" not in os.listdir(resourceDir+ "/"):
        os.makedirs(resourceDir+ "/output_graphs", exist_ok=True)

    print("Building vocab...")
    # read and clean definitions
    fill_vocabulary_file("/input/Definitions.csv")

    print("OK.")

    ### init some variables
    global_dict = read_input_files()

    doi_graph = Graph(identifier=CODA.Dois)

    # map of (paperID : doi)
    papers2dois = { key:val for key, val in zip(global_dict['papers']['paper_ID'],global_dict['papers']['doi']) if val != 'NA' or val != "" }

    errorSet = set()

    # checks and remove study duplicates if any
    #print ("Duplicates study ID :", set(pd.concat(g['study_ID'] for _, g in global_dict['studies'].groupby("study_ID") if len(g) > 1) ))
    studies = global_dict['studies'].drop_duplicates(subset='study_ID', keep='first').set_index('study_ID').to_dict('index')

    # init classes to build graphs
    study_graph_builder = StudyBuilder()
    effect_graph_builder = EffectBuilder()
    treatment_graph_builder = TreatmentBuilder()
    vocabMngr = VocabularyManager(resourceDir+"/input/codebook_clean.csv")

    in_graph_papers  = list()
    missing_dois = set()

    list_of_studies = list()
    list_of_papers =  list()
    papers_and_studies = dict()

    # for study in studies:
#         new_study_uri = URIRef(CODA['id/']+study)
#         print(study)
#         study_graph_builder.build_study_info(new_study_uri , studies[study])


    #loop over treatments :
    print("Iterating over treatments....")
    for ix, treatment_row in tqdm(global_dict['trts'].iterrows()):

        # (1) treatments
        # print(ix,treatment_row['treatment_ID'])

        ###
        if ";" in treatment_row['treatment_ID']:
            errorSet.add((treatment_row['treatment_ID'],"",""))
            print("Study %s has wrong syntax" % treatment_row['treatment_ID'])
            continue

        ### for testing
        # if ix > 10 : break

        treatment_graph_builder.build_treatment(treatment_row)

        # add it to paper list
        if treatment_row['study_ID'].split("_")[0] not in papers_and_studies.keys():
            papers_and_studies[treatment_row['study_ID'].split("_")[0]] = list()

        if treatment_row['study_ID'] not in papers_and_studies[treatment_row['study_ID'].split("_")[0]] :
            papers_and_studies[treatment_row['study_ID'].split("_")[0]].append(treatment_row['study_ID'])


    # (4) effect sizes (this could be done in treatment loop?)
    print("Iterating over effects....")
    for ix,effect_row in tqdm(global_dict['es'].iterrows()):

        # if ix > 10 : break
        # print(ix, effect_row['effect_ID'])

        if ";" in effect_row['treatment_1'] or ";" in effect_row['treatment_2'] :
            # quick & dirty fix / TODO : remove error
            continue

        effect_graph_builder.build_effect(effect_row)

        if effect_row['study_ID'].split("_")[0] not  in list_of_papers :
            list_of_papers.append(effect_row['study_ID'].split("_")[0])

        if effect_row['study_ID'] not in list_of_studies :
            list_of_studies.append(effect_row['study_ID'])


    #(5) finally papers and studies
    print("Iterating over studies....")
    for paperno in tqdm(papers_and_studies.keys()):

        new_paper = URIRef(CODA['id/']+paperno)
        study_graph_builder.add_triple((new_paper, RDF.type, coda_class.Paper))
        study_graph_builder.add_triple((new_paper, RDFS.label, Literal("Paper %s" % paperno )))

        for study in papers_and_studies[paperno]:
            # print(paperno, study)

            new_study_uri = URIRef(CODA['id/']+study)

            study_graph_builder.add_triple((new_study_uri, RDF.type, coda_class.Study))
            # TODO : studies should be replaced
            study_graph_builder.build_study_info(new_study_uri , studies[study])

            study_graph_builder.add_triple((URIRef(CODA['id/']+study.split("_")[0]), coda_prop.study, new_study_uri))
            study_graph_builder.add_triple((new_study_uri, RDF.type, coda_class.Study))
            study_graph_builder.add_triple((new_study_uri, RDFS.label, Literal("Study %s" % study ) ))

        if paperno in papers2dois.keys() and paperno not in in_graph_papers and papers2dois[paperno]:
            in_graph_papers.append(paperno)

            if "<" in papers2dois[paperno] or ">" in papers2dois[paperno] or "#" in papers2dois[paperno] or " " in papers2dois[paperno] :
                paper_doi = papers2dois[paperno].replace("<","&lt").replace(">","&gt").replace("#","%23").replace(" ","")
            else :
                paper_doi = papers2dois[paperno]

            study_graph_builder.add_triple((new_paper, coda_prop.doi, URIRef("http://dx.doi.org/%s" %  paper_doi) ))

            # NB : folder contains more DOIs than the ones in the paper list
            if paperno+".n3" in os.listdir(resourceDir+ "/input/dois") :
                new_doi_graph = Graph()

                try:
                    new_doi_graph.parse(resourceDir+ "/input/dois/%s.n3" % paperno, format="nt" )

                    if len(new_doi_graph) <= 1 :
                        print(paperno)
                        missing_dois.add(paperno)
                        pass
                except SAXParseException :
                    print( "[ERR] Malformed file %s.n3" % paperno)
                except ParseError :
                    print( "[ERR] Parse error for %s.n3" % paperno)
                    pass
                doi_graph+=new_doi_graph

                doi_graph.add((URIRef("http://dx.doi.org/%s" % paper_doi), RDF.type, coda_class.DOI )) # give DOIs a type

            else :
                missing_dois.add(paperno)



    #finally add countries to graph
    vocabMngr.addCountryListToGraph()


    """
    save outputs
    """
    print("Saving graphs...")

    save_graph(vocabMngr.get_graph(),resourceDir+ "/output_graphs/vocabulary.trig")

    save_graph(study_graph_builder.get_graph(),resourceDir+"/study_graph_temp.trig")
    # rdflib prints gYear as YYYY-MM-DD, the below removes -MM-DD from it (could be probably done in a different way )
    os.system("sed 's/\-[0-9][0-9]\-[0-9][0-9]\"\^\^xsd:gYear/\"\^\^xsd:gYear/g' "+resourceDir+"/study_graph_temp.trig >| "+resourceDir+"/output_graphs/study_graph.trig   ")
    os.remove(resourceDir+"/study_graph_temp.trig")
    os.remove(resourceDir+"/input/codebook_clean.csv")

    save_graph(effect_graph_builder.get_graph(),resourceDir+ "/output_graphs/effect_graph.trig")
    save_graph(treatment_graph_builder.get_graph(),resourceDir+ "/output_graphs/treatment_graph.trig")

    save_graph(doi_graph, resourceDir+ "/output_graphs/dois_graph.trig")

    """
    report errors
    """

    print("\n\n######### Error log: \n")
    #  this *should* check vocabulary usage in graphs and log errors
    with open('errors.csv','w') as f:
        for i in errorSet:
            f.write("%s,%s,%s,%s\n" % (i[0].split("/")[-1],i[1].split("/")[-1], i[2].split("/")[-1] , i[3].split("/")[-1] ))
            print ("%s,%s,%s,%s\n" % (i[0].split("/")[-1],i[1].split("/")[-1], i[2].split("/")[-1] , i[3].split("/")[-1] ))
    f.close()

    print ("Missing %d DOIs, from list : %s" % (len(missing_dois), str(missing_dois)))

    print("Done.")
