library(devtools)
install_github("tmalsburg/scanpath/scanpath", dependencies=TRUE)
library(tidyverse)
library(magrittr)
# library(scanpath)
library(stringr)
library(Rtsne)
source("text_metrics/scanpath-visualization/comparative-reread-streamlit-viz/plot_scanpaths.R")

fixations = read.csv(
    "ln_shared_data/onestop/processed/fixation_data_enriched_360_05052024.csv"
)

# define a break_down_unique_paragraph_id that takes the textual value and breaks it down by "_" to the new columns: batch, article_id, level, paragraph_id
fixations$break_down_unique_paragraph_id = strsplit(fixations$unique_paragraph_id, "_")
fixations$batch = as.numeric(sapply(fixations$break_down_unique_paragraph_id, function(x) x[1]))
fixations$article_id = as.numeric(sapply(fixations$break_down_unique_paragraph_id, function(x) x[2]))
fixations$level = as.factor(sapply(fixations$break_down_unique_paragraph_id, function(x) x[3]))
fixations$paragraph_id = as.numeric(as.factor(sapply(fixations$break_down_unique_paragraph_id, function(x) x[4])))

fixations$trial = paste(fixations$subject_id, fixations$article_ind, fixations$paragraph_id, fixations$has_preview, fixations$unique_paragraph_id, fixations$q_ind, fixations$abcd_answer, sep="__")
fixations$trial_id = as.numeric(as.factor(fixations$trial))

fixations$sub_cond = paste(fixations$subject_id, fixations$has_preview, sep="__") # for hunting/gathering plots

# Filter out unused columns
s_fixations = fixations[, c(
    "trial",
    "trial_id",
    "subject_id",
    'sub_cond',
    "CURRENT_FIX_INTEREST_AREA_INDEX",
    "CURRENT_FIX_DURATION",
    "has_preview",
    "CURRENT_FIX_X",
    "CURRENT_FIX_Y",
    "unique_paragraph_id",
    "q_ind",
    "reread",
    'abcd_answer',
    "article_id",
    "paragraph_id",
    "article_ind"
  )
]



# for each combination of subject_id, article_ind, article_id, paragraph_id, q_ind, abcd_answer do the following:
# get small which is the subset of fixations where the subject_id is the same as the current subject_id
# iterate over article_ind (1-12), paragraph_id (max in each article)
# run plot_scanpaths(small_small, CURRENT_FIX_DURATION ~ CURRENT_FIX_X + CURRENT_FIX_Y) and save with the name according to the combination stated above

#!#1! set the x and y limits
max_x = 2560
max_y = 1440

base_path = "/data/home/meiri.yoav/Cognitive-State-Decoding/ln_shared_data/onestop/trial_plots/"

i = 0
for (subj_id_val in unique(fixations$subject_id)) {
  # create a directory for the subject_id
  fixations_sub = subset(fixations, subject_id == subj_id_val)
  subj_path = paste0(base_path, subj_id_val, "/")
  dir.create(file.path(subj_path), showWarnings = FALSE)
  
  for (article_ind_val in 1:12) {
    # create a directory for the article_id
    fixations_sub_article = fixations_sub %>% filter(article_ind == article_ind_val)
    article_id = unique(fixations_sub_article$article_id)
    subj_article_path = paste0(base_path, subj_id_val, "/", article_ind_val, "/")
    # dir.create(file.path(subj_article_path), showWarnings = FALSE)
    
    for (paragraph_id_val in 1:max(fixations_sub_article$paragraph_id)) {
      tryCatch({
        small <- subset(fixations_sub_article, paragraph_id == paragraph_id_val)
        trial <- unique(small$trial)
        p <- invisible(plot_scanpaths(small, CURRENT_FIX_DURATION ~ CURRENT_FIX_X + CURRENT_FIX_Y | trial, subj_id_val))
        
        # Set the x and y limits
        p <- p + xlim(0, max_x) + scale_y_reverse() + ylim(max_y, 0)
        
        # Save the plot
        ggsave(paste0(subj_path, "/scanpath_", trial, ".png"), plot = p)
      }, error = function(e) {
        message("An error occurred: ", e$message)
      })

    }
  }
  i = i + 1
  print(i)
  print(subj_id_val)
}
