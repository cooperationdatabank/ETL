###############################################################################
# CODA: DATA WRANGLING AND EFFECT SIZE COMPUTATION ############################
# SIMON COLUMBUS | 2020-06-26 #################################################
###############################################################################


for (p in c("data.table", "esc", "tidyverse")) {
  if (!require(p, character.only = T)) {
    install.packages(p)
    require(p,character.only=TRUE)
  }
}



# LOAD PACKAGES ###############################################################
library(data.table)
library(esc)
library(tidyverse)

#local path
path = Sys.getenv("TRIPLY__PATHS__DATA_DIR")
srcDir = Sys.getenv("TRIPLY_ETL_SRC")
# load ES functions
source(paste0(srcDir,"/EffectSizeFunctions.R"))

# LOAD DATA ###################################################################
keepingTrack <- read.csv(paste0(path,"/input/Keeping_Track.csv"), # Keeping track
                         stringsAsFactors = FALSE) %>%
  # Remove un-checked studies
  filter(!is.na(study_ID) & grepl("4", Re.Checks))
studyCharacteristics <- read.csv(paste0(path,"/input/Study_characteristics.csv"),
                                 stringsAsFactors = FALSE, # Study characteristics
                                 check.names=FALSE,
                                 colClasses=c(rep(NA, 54), rep("NULL", 71),
                                              rep(NA, 2), "NULL", NA, rep("NULL", 26))) %>% # Drop unused columns
  filter(!is.na(study_ID) & !(study_ID == FALSE)) %>%
  filter(`Dilemma type(s)` %in% 1:3) %>%
  distinct(., study_ID, .keep_all = TRUE) # Remove duplicates
treatments <- read.csv(paste0(path,"/input/Treatments.csv"), # Treatments
                       stringsAsFactors = FALSE,
                       check.names=FALSE) %>%
  filter(!is.na(treatment_ID) & treatment_ID != "") %>%
  # Filter out treatments from unchecked studies
  filter(study_ID %in% keepingTrack$study_ID) %>%
  mutate(`n f` = ifelse(!is.na(Remove) & Remove == 1, -1, `n f`)) %>%
  mutate(`n f` = replace_na(`n f`, 0)) %>%
  filter(!(`n f` == -1 | `n f` == -2))  # Remove deleted treatments
ontology <- read.csv(paste0(path,"/input/Ontology.csv"),
                     stringsAsFactors = FALSE, skip = 1,
                     check.names=FALSE) %>% # Ontology annotation
  filter(!is.na(treatment_ID)) %>%               # Removes notes at the bottom
  distinct(., study_ID, variable_ID, treatment_ID, # Remove duplicates
           .keep_all = TRUE)
# MERGE DATA ##################################################################

data <- treatments %>%
  merge(., studyCharacteristics,
        by = c("study_ID"),
        suffixes = c("", "_char")) %>%
  merge(., ontology,
        by = c("study_ID", "variable_ID", "treatment_ID"),
        suffixes = c("", "_ont")) %>%
  #dplyr::select(., !ends_with("_char") & !ends_with("_ont")) %>% # Remove duplicate columns
  select(study_ID:treatment_ID,
         Published_ES:`Study #`,
         `Overlaps with...`:`N.obs/N`,
         IV_description:SD,
         Agent_Role:OtherCoding)

# DATA CLEANING ###############################################################

# Clean up data for computing effect sizes
# This is mostly converting to numeric vectors and removing invalid entries.
dataClean <- data %>%
  mutate_at(vars(`Overall P(C)`:`P(E) contributed`,
                 `BS/WS`, df1:p, ES,
                 n:SD),
            funs(as.numeric(as.character(.)))) %>%
  mutate(p = ifelse(p == 0 | p == 1 | p > 1, "N/A", p)) %>% # Remove invalid p-values
  mutate_if(is.logical, as.character) %>% # mutate logical columns ()
  mutate_if(is.character, funs(recode(na_if(.,""), `N/A` = "-999", MISSING = "-999", `999` = "-999", .missing = "-999"))) %>%
  mutate_if(is.integer, funs(recode(., `999` = -999L))) %>%
  mutate_if(is.double, funs(recode(., `999` = -999.0))) %>%
  mutate_all(funs(replace(., is.na(.), -999))) %>%
  select(-`If other Recr_Meth: Specify`, # Drop unused columns
         -`Iterated # per block:`,
         -`Block #:`,
         -Feedback,
         -IV_description, -DV, -Level, -Agent_Role)

# Compute additional treatment-level variables:
# Proportion of endowment contributed, log-transformed proportion of endowment
# contributed/rate of cooperation and coefficient of variation.

dataClean <- dataClean %>%
  # For single-treatment variables with missing M/P(C)/n, replace the
  # treatment-level value with the study-level value (unless they are
  # coded as a subset in Main Effect / Interaction).
  mutate(M = case_when(M != -999 ~ M,
                       M == -999 & `# Levels` == -999 & !(`Main Effect / Interaction` %in% c(3, 4)) & DV_behavior == "Contribution" ~ 
                         `Overall M cooperation`,
                       M == -999 & `# Levels` == -999 & !(`Main Effect / Interaction` %in% c(3, 4)) & DV_behavior == "Withdrawals" ~ 
                         `Overall M withdrawal`,
                       TRUE ~ -999),
         `P(C)` = case_when(`P(C)` != -999 ~ `P(C)`,
                            `P(C)` == -999 & `# Levels` == -999 & !(`Main Effect / Interaction` %in% c(3, 4)) & DV_behavior == "Cooperation" ~ 
                              `Overall P(C)`,
                            TRUE ~ -999),
         n = case_when(n != -999 ~ n,
                       n == -999 & `# Levels` == -999 & !(`Main Effect / Interaction` %in% c(3, 4)) ~ `N.obs/N`,
                       TRUE ~ -999)) %>%
  mutate(`P(C)` = ifelse(`P(C)` > 1, NA, `P(C)`)) %>%
  mutate(proportionOfEndowmentContributed = case_when(DV_behavior == "Contribution" & M != -999 & `Choice range upper` != -999 & `Choice range lower` != -999 ~ 
                                                        (M-as.numeric(`Choice range lower`))/(as.numeric(`Choice range upper`)-as.numeric(`Choice range lower`)),
                                                      DV_behavior == "Withdrawals" & M != -999 & `Choice range upper` != -999 ~ 
                                                        (as.numeric(`Choice range upper`) - M)/(as.numeric(`Choice range upper`)-as.numeric(`Choice range lower`)),
                                                      TRUE ~ -999)) %>%
  mutate(logPropContributed = case_when(`P(C)` != -999 ~ log(`P(C)`/(1 - `P(C)`)),
                                        proportionOfEndowmentContributed != -999 ~ log(proportionOfEndowmentContributed/(1 - proportionOfEndowmentContributed)),
                                        TRUE ~ -999),
         coefficientOfVariation = case_when(`P(C)` != -999 & n != -999 ~ 1 / (n * `P(C)`) + 1 / (n * (1 - `P(C)`)),
                                            DV_behavior == "Contribution" & proportionOfEndowmentContributed != -999 & SD != -999 ~ 
                                              (((SD^2) / ((M - as.numeric(`Choice range lower`))^2)) * 1 / (((1 - proportionOfEndowmentContributed)^2) * n)),
                                            DV_behavior == "Withdrawals" & proportionOfEndowmentContributed != -999 & SD != -999 ~ 
                                              (((SD^2) / ((as.numeric(`Choice range upper`) - M - as.numeric(`Choice range lower`))^2)) * 1 / (((1 - proportionOfEndowmentContributed)^2) * n)))) %>%
  select(study_ID:SD,proportionOfEndowmentContributed:coefficientOfVariation,everything())

# OBSERVATION-LEVEL DATA FRAME ################################################

# Create data frame with one row per observation, i.e., per possible
# combination of treatments within a variable. Treatments are denoted
# treatment_1 and treatment_2 within each observation, based on their
# treatment_ID.

# Separate variables with a single treatment from those with multiple
# treatments.

dataNomiss <- dataClean %>%
  mutate_at(vars(`Overall P(C)`:`P(E) contributed`, # Define NAs
                 `BS/WS`:SD),
            funs(na_if(., -999)))

# First set, variables with exactly one treatment.
# For these variables, the second treatment is empty.
dataOneTreatment <- dataNomiss %>%
  group_by(variable_ID) %>%
  filter(n() == 1) %>%
  ungroup() %>%
  select(variable_ID, treatment_ID) %>%
  dplyr::rename(treatment_1 = treatment_ID) %>%
  mutate(treatment_2 = NA)       # Set the second treatment to NA

# Second set, variables with more than one treatment
dataMultiTreatment <- dataNomiss %>%
  group_by(variable_ID) %>%
  filter(n() > 1)                # Exclude variable_IDs with a single treatment

# Get a data.table with every combination of treatment_IDs
# within each variable_ID
dataMultiTreatment <- setDT(dataMultiTreatment)[,
                                                {i1 <-  combn(treatment_ID, 2)
                                                list(i1[1,], i1[2,]) },
                                                by =  variable_ID]

# Merge dataMultiTreatment and dataOneTreatment
dataMultiTreatment <- dataMultiTreatment %>%
  dplyr::rename(treatment_1 = V1,
                treatment_2 = V2) %>%
  rbind(., dataOneTreatment)

# Merge the treatment indicators with data and generate unique effect_IDs
dataEffects <- merge(dataMultiTreatment, dataNomiss,
                     by.x = c("variable_ID", "treatment_1"),
                     by.y = c("variable_ID", "treatment_ID"),
                     all.x = TRUE) %>%
  merge(., data.frame(dataNomiss[,c("treatment_ID", "n", "P(C)", "M", "SD")]),
        by.x = "treatment_2", by.y = "treatment_ID",
        all.x = TRUE, suffixes = c(".t1", ".t2")) %>%
  rename(`P(C).t1` = `P(C)`,
         `P(C).t2` = `P.C.`) %>%
  mutate(effect_ID = ifelse(is.na(treatment_2), paste0(treatment_1, ".0"),
                            paste(treatment_1, sub("^.*\\.", "",
                                                   treatment_2), sep="."))) %>%
  select(study_ID, variable_ID, effect_ID,
         treatment_1, treatment_2,
         `Author(s) + year`:SD.t1,
         n.t2:SD.t2,everything())

# COMPUTING EFFECT SIZES ######################################################

# Effect size computation #####################################################

# Function to compute effect sizes.
# Takes a data.frame (specifically, dataNomiss)
# The specific effect size functions are hard-coded in effectSizeFunctions;
# right now, only es_from_means, es_from_prop, and es_from_rn are used.
# Output is a data.frame with effectSizeEstimate and effectSizeVar; also
# returned are effectSizeMeasure and effectSizeAlgorithm.
computeEffectSizes <- function(data){

  # Functions for effect-size computation for between-subjects designs are
  # hardcoded:
  effectSizeFunctions = list(es_from_means,
                             es_from_tn,
                             es_from_tdf,
                             es_from_prop,
                             es_from_rn,
                             es_from_means_dep)

  # computeEstimates iterates over the provided effectSizeFunctions
  # and applies them to the given data.frame and effect size measure.
  computeEstimates <- function(data, effsize) {
    effectSizes <- lapply(effectSizeFunctions, function(f) f(data, effsize)) %>%
      Reduce(function(x, y) merge(x, y, by="study", all=TRUE), .)

    # Name the columns.
    # Note that depending on the effect size measure, different numbers of
    # columns are generated.
    if(effsize == "r"){
      names(effectSizes) <- setdiff(c("study",
                                      paste(rep(c("means", "tn", "tdf", "prop", "rn", "means_dep"),
                                                each = 11),
                                            rep(c("es", "weight", "sample.size", "se",
                                                  "var", "ci.lo", "ci.hi", "fishersz",
                                                  "ci.lo.z", "ci.hi.z", "measure"),
                                                times = length(effectSizeFunctions)),
                                            sep = "_")),
                                    paste(rep(c("rn", "tn", "tdf", "means_dep"), each = 3),
                                          c("fishersz", "ci.lo.z", "ci.hi.z"), sep = "_"))
    }
    else{
      names(effectSizes) <- c("study",
                              paste(rep(c("means", "tn", "tdf", "prop", "rn", "means_dep"),
                                        each = 8),
                                    rep(c("es", "weight", "sample.size", "se",
                                          "var", "ci.lo", "ci.hi", "measure"),
                                        times = length(effectSizeFunctions)),
                                    sep = "_"))
    }
    return(effectSizes)
  }

  # Compute estimates of Cohen's d
  effectSizeD <- data %>%
    computeEstimates(data = ., effsize = "d") %>%
    dplyr::select(study,
                  ends_with("_es"),
                  ends_with("_var"),
                  ends_with("ci.lo"),
                  ends_with("ci.hi"),
                  ends_with("sample.size"),
                  ends_with("_measure")) %>%
    mutate(effect_ID = study,
           effectSizeEstimate = case_when(!is.na(means_dep_es) ~ means_dep_es,
                                          !is.na(means_es) ~ means_es,
                                          !is.na(tn_es) ~ tn_es,
                                          !is.na(tdf_es) ~ tdf_es,
                                          !is.na(prop_es) ~ prop_es,
                                          !is.na(rn_es) ~ rn_es),
           effectSizeVariance = case_when(!is.na(means_dep_es) ~ means_dep_var,
                                          !is.na(means_es) ~ means_var,
                                          !is.na(tn_es) ~ tn_var,
                                          !is.na(tdf_es) ~ tdf_var,
                                          !is.na(prop_es) ~ prop_var,
                                          !is.na(rn_es) ~ rn_var),
           effectSizeLowerLimit = case_when(!is.na(means_dep_es) ~ means_dep_ci.lo,
                                            !is.na(means_es) ~ means_ci.lo,
                                            !is.na(tn_es) ~ tn_ci.lo,
                                            !is.na(tdf_es) ~ tdf_ci.lo,
                                            !is.na(prop_es) ~ prop_ci.lo,
                                            !is.na(rn_es) ~ rn_ci.lo),
           effectSizeUpperLimit = case_when(!is.na(means_dep_es) ~ means_dep_ci.hi,
                                            !is.na(means_es) ~ means_ci.hi,
                                            !is.na(tn_es) ~ tn_ci.hi,
                                            !is.na(tdf_es) ~ tdf_ci.hi,
                                            !is.na(prop_es) ~ prop_ci.hi,
                                            !is.na(rn_es) ~ rn_ci.hi),
           effectSizeSampleSize = case_when(!is.na(means_dep_es) ~ means_dep_sample.size,
                                            !is.na(means_es) ~ means_sample.size,
                                            !is.na(tn_es) ~ tn_sample.size,
                                            !is.na(tdf_es) ~ tdf_sample.size,
                                            !is.na(prop_es) ~ prop_sample.size,
                                            !is.na(rn_es) ~ rn_sample.size),
           effectSizeMeasure = "d",
           effectSizeAlgorithm = case_when(!is.na(means_dep_es) ~ "means_dep",
                                           !is.na(means_es) ~ "means",
                                           !is.na(tn_es) ~ "tn",
                                           !is.na(tdf_es) ~ "tdf",
                                           !is.na(prop_es) ~ "prop",
                                           !is.na(rn_es) ~ "rn")) %>%
    select(effect_ID, effectSizeEstimate:effectSizeAlgorithm)

  # Compute estimates of r
  effectSizeR <- data %>%
    computeEstimates(data = ., effsize = "r") %>%
    dplyr::select(study,
                  ends_with("_es"),
                  ends_with("_var"),
                  ends_with("ci.lo"),
                  ends_with("ci.hi"),
                  ends_with("sample.size"),
                  ends_with("_measure")) %>%
    mutate(effect_ID = study,
           effectSizeEstimate = case_when(!is.na(rn_es) ~ rn_es,
                                          !is.na(means_es) ~ means_es,
                                          !is.na(tn_es) ~ tn_es,
                                          !is.na(tdf_es) ~ tdf_es,
                                          !is.na(prop_es) ~ prop_es),
           effectSizeVariance = case_when(!is.na(rn_es) ~ rn_var,
                                          !is.na(means_es) ~ means_var,
                                          !is.na(tn_es) ~ tn_var,
                                          !is.na(tdf_es) ~ tdf_var,
                                          !is.na(prop_es) ~ prop_var),
           effectSizeLowerLimit = case_when(!is.na(rn_es) ~ rn_ci.lo,
                                            !is.na(means_es) ~ means_ci.lo,
                                            !is.na(tn_es) ~ tn_ci.lo,
                                            !is.na(tdf_es) ~ tdf_ci.lo,
                                            !is.na(prop_es) ~ prop_ci.lo),
           effectSizeUpperLimit = case_when(!is.na(rn_es) ~ rn_ci.hi,
                                            !is.na(means_es) ~ means_ci.hi,
                                            !is.na(tn_es) ~ tn_ci.hi,
                                            !is.na(tdf_es) ~ tdf_ci.hi,
                                            !is.na(prop_es) ~ prop_ci.hi),
           effectSizeSampleSize = case_when(!is.na(rn_es) ~ rn_sample.size,
                                            !is.na(means_es) ~ means_sample.size,
                                            !is.na(tn_es) ~ tn_sample.size,
                                            !is.na(tdf_es) ~ tdf_sample.size,
                                            !is.na(prop_es) ~ prop_sample.size),
           effectSizeMeasure = "r",
           effectSizeAlgorithm = case_when(!is.na(rn_es) ~ "rn",
                                           !is.na(means_es) ~ "means",
                                           !is.na(tn_es) ~ "tn",
                                           !is.na(tdf_es) ~ "tdf",
                                           !is.na(prop_es) ~ "prop")) %>%
    select(effect_ID, effectSizeEstimate:effectSizeAlgorithm)

  # Combine estimates for d and r
  effectSizes <- rbind(effectSizeD, effectSizeR)
  
  # treatment_IDs with DV_behavior == "Withdrawals"
  withdrawals <- data %>% filter(DV_behavior == "Withdrawals")

  # Merge in treatment_IDs and DV specification.
  effectSizes <- data %>%
    dplyr::select(study_ID, effect_ID, treatment_1, treatment_2,
                  DV_behavior, DV_periods, DV_percentage) %>%
    merge(., effectSizes, by = "effect_ID", all.x = TRUE) %>%
    mutate(effect_ID = ifelse(is.na(effectSizeMeasure),
                              paste(effect_ID, "0", sep = "."),
                              paste(effect_ID, effectSizeMeasure, sep = "."))) %>%
    # Invert effect sizes from withdrawals
    mutate(esLL = effectSizeLowerLimit,
           esUL = effectSizeUpperLimit) %>%
    mutate(effectSizeEstimate = case_when(treatment_1 %in% withdrawals$treatment_1 ~ -effectSizeEstimate,
                                          TRUE ~ effectSizeEstimate),
           effectSizeLowerLimit = case_when(treatment_1 %in% withdrawals$treatment_1 ~ esUL,
                                            TRUE ~ esLL),
           effectSizeUpperLimit = case_when(treatment_1 %in% withdrawals$treatment_1 ~ esLL,
                                            TRUE ~ esUL)) %>%
    select(-esLL, -esUL)

  return(effectSizes)
}

# Compute effect sizes
effectSizes <- computeEffectSizes(dataEffects)

# Output files

write.csv(x=effectSizes, file=paste0(path,"/input/effect_sizes_computed.csv"))

write.csv(x=dataClean, file=paste0(path,"/input/data_clean.csv"), na="", quote=TRUE)
