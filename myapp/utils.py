import re
import pandas as pd
import joblib
import nltk
from nltk.tokenize import RegexpTokenizer
from nltk.corpus import stopwords
from textblob import Word
import os

# Download required NLTK data
nltk.download('stopwords')
nltk.download('wordnet')

class TextClassifier:
    def __init__(self):
        self.model = None
        self.count_vec = None
        self.transformer = None
        self.load_models()
    
    def load_models(self):
        model_path = os.path.join(os.path.dirname(__file__), '../models/Text_LR.pkl')
        count_vec_path = os.path.join(os.path.dirname(__file__), '../models/count_vect.pkl')
        transformer_path = os.path.join(os.path.dirname(__file__), '../models/transformer.pkl')
        
        self.model = joblib.load(model_path)
        self.count_vec = joblib.load(count_vec_path)
        self.transformer = joblib.load(transformer_path)
    
    def preprocess_text(self, text):
        text_df = pd.DataFrame({'text': [text]})
        
        # Lowercase and clean
        text_df['lower_case'] = text_df['text'].apply(
            lambda x: x.lower().strip().replace('\n', ' ').replace('\r', ' ')
        )
        
        # Remove non-alphabetic characters
        text_df['alphabetic'] = text_df['lower_case'].apply(
            lambda x: re.sub(r'[^a-zA-Z\']', ' ', x)
        ).apply(
            lambda x: re.sub(r'[^\x00-\x7F]+', '', x)
        )
        
        # Tokenize
        tokenizer = RegexpTokenizer(r'\w+')
        text_df['special_word'] = text_df.apply(
            lambda row: tokenizer.tokenize(row['alphabetic']), axis=1
        )
        
        # Remove stopwords
        stop = [word for word in stopwords.words('english') if word not in ["my", "haven't"]]
        text_df['stop_words'] = text_df['special_word'].apply(
            lambda x: [item for item in x if item not in stop]
        )
        
        # Remove short words
        text_df['stop_words'] = text_df['stop_words'].astype('str')
        text_df['short_word'] = text_df['stop_words'].str.findall(r'\w{2,}')
        
        # Join tokens
        text_df['text'] = text_df['short_word'].str.join(' ')
        
        # Lemmatize
        text_df['text'] = text_df['text'].apply(
            lambda x: " ".join([Word(word).lemmatize() for word in x.split()])
        )
        
        return text_df['text'][0]
    
    def predict(self, text):
        # Preprocess text
        processed_text = self.preprocess_text(text)
        
        # Transform text
        text_vec = self.count_vec.transform([processed_text])
        text_tfidf = self.transformer.transform(text_vec)
        
        # Make prediction
        prediction = self.model.predict(text_tfidf)
        prediction_proba = self.model.predict_proba(text_tfidf)
        
        return prediction[0], prediction_proba[0]

# Global classifier instance
classifier = TextClassifier()
