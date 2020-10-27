###############################################################################
# Comparing two independent samples ###########################################
###############################################################################

# Effect size for comparison of two independent groups ########################
# Computed from means, standard deviations, and sample sizes
es_from_means = function(data, effsize){
  es_from_means <- data %>%
    filter(`BS/WS` == 1 &
             !(SD.t1 == 0 | SD.t2 == 0) &
             (`Main Effect / Interaction` == 1 |
                `Main Effect / Interaction` == 3)) %>%
    dplyr::select(effect_ID, 
                  M.t1, M.t2, SD.t1, SD.t2, n.t1, n.t2) %>%
    drop_na() %>%
    effect_sizes(grp1m = M.t1, grp1sd = SD.t1, grp1n = n.t1, 
                 grp2m = M.t2, grp2sd = SD.t2, grp2n = n.t2,
                 study = effect_ID, 
                 fun = "esc_mean_sd",
                 es.type = effsize)
}

# Effect size for comparison of two independent groups ########################
# Computed from t-statistics and sample sizes
# If Direction == 1, the t value should be negative; 
# if Direction == 0, the t value should be positive; 
# otherwise invert the t statistic.
es_from_tn = function(data, effsize){
  es_from_means <- data %>%
    filter(`BS/WS` == 1 &
             Test == "t" &
             `# Levels` == 2 &
             (`Main Effect / Interaction` == 1 |
                `Main Effect / Interaction` == 3)) %>%
    dplyr::select(effect_ID, 
                  Statistics, n.t1, n.t2, Direction) %>%
    mutate(Statistics = case_when(Direction == 1 & Statistics > 0 ~ -Statistics,
                                  Direction == 0 & Statistics < 0 ~ Statistics * (-1))) %>%
    drop_na() %>%
    effect_sizes(grp1n = n.t1, grp2n = n.t2, t = Statistics,
                 study = effect_ID, 
                 fun = "esc_t",
                 es.type = effsize)
  return(es_from_means) }

# Cohen's d for two independent groups ########################################
# Computed from t-statistics and degrees of freedom
es_from_tdf = function(data, effsize){
  es_from_means <- data %>%
    mutate(df1 = df1 + 1) %>%
    filter(`BS/WS` == 1 &
             Test == "t" &
             `# Levels` == 2 &
             (`Main Effect / Interaction` == 1 |
                `Main Effect / Interaction` == 3)) %>%
    dplyr::select(effect_ID, 
                  Statistics, df1) %>%
    drop_na() %>%
    effect_sizes(totaln = df1, t = Statistics,
                 study = effect_ID, 
                 fun = "esc_t",
                 es.type = effsize)
  return(es_from_means) }

# Effect size for comparison of two independent groups ########################
# Computed from proportions and sample sizes
es_from_prop = function(data, effsize){
  es_from_prop <- data %>%
    filter(`BS/WS` == 1 &
             !(is.na(`P(C).t1`) | is.na(`P(C).t2`)) &
             (`Main Effect / Interaction` == 1 |
                `Main Effect / Interaction` == 3)) %>%
    dplyr::select(effect_ID, 
                  `P(C).t1`, `P(C).t2`, n.t1, n.t2) %>%
    drop_na() %>%
    effect_sizes(prop1event = `P(C).t1`, grp1n = n.t1, 
                 prop2event = `P(C).t2`, grp2n = n.t2,
                 study = effect_ID, 
                 fun = "esc_bin_prop",
                 es.type = effsize)
}

###############################################################################
# Comparing two dependence samples ############################################
###############################################################################

es_from_means_dep <- function(data, effsize){
  es_from_means_dep <- data %>%
    filter(`BS/WS` == 2 &
             !(SD.t1 == 0 | SD.t2 == 0) &
             (`Main Effect / Interaction` == 1 |
                `Main Effect / Interaction` == 3) &
             n.t1 == n.t2) %>%
    dplyr::select(effect_ID, 
                  M.t1, M.t2, SD.t1, SD.t2, n.t1, n.t2) %>%
    drop_na() %>%
    mutate(r = 0.5,
           study = effect_ID,
           es = (M.t1-M.t2) / sqrt(SD.t1^2 + SD.t2^2 - 2 * r * SD.t1 * SD.t2),
           weight = NA,
           sample.size = n.t1,
           se = NA,
           var = (1/n.t1) + (es^2 / (2*n.t1)),
           ci.lo = es - 1.96*(sqrt(var)/sqrt(sample.size)),
           ci.hi = es + 1.96*(sqrt(var)/sqrt(sample.size)),
           measure = effsize) %>%
    select(study:measure)
}

###############################################################################
# Correlations ################################################################
###############################################################################

# Effect size for association of two continuous variables
# Computed from correlation coefficient and sample sizes
es_from_rn = function(data, effsize){
  es_from_rn <- data %>%
    filter(`Effect size measure` == "r") %>%
    mutate(n.t1 = ifelse(is.na(n.t1), N, n.t1)) %>%
    select(effect_ID, ES, n.t1) %>%
    drop_na() %>%
    mutate(var_r = (1 - ES^2)/(n.t1 - 2),
           measure = effsize) %>%
    mutate(study = effect_ID,
           es = ifelse(measure == "r", ES,
                       ifelse(measure == "d", (2*ES)/sqrt(1-ES^2), NA)),
           weight = NA,
           sample.size = n.t1,
           var = ifelse(measure == "r", var_r,
                        ifelse(measure == "d", (4*var_r)/(1-ES^2)^3, NA)),
           se = NA,
           ci.lo = es - 1.96 * sqrt(var/sample.size),
           ci.hi = es + 1.96 * sqrt(var/sample.size)) %>%
    select(study, es, weight, sample.size, se, var, ci.lo, ci.hi, measure)
}