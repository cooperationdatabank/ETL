
for (p in c("data.table", "esc", "tidyverse")) {
  if (!require(p, character.only = T)) {
    install.packages(p)
    require(p,character.only=TRUE)
  }
}
