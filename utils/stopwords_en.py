# utils/stopwords_en.py
import nltk
from nltk.corpus import stopwords

# Make sure NLTK stopwords are downloaded
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

EN_STOPWORDS = set(stopwords.words('english'))
