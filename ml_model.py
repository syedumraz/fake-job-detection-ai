"""
AI Against Fraud: Intelligent Detection of Fake Job Listings
Advanced ML Algorithm for Online Recruitment Scam Detection
"""

import os
import json
from datetime import datetime


class FakeJobPostDetector:
    """
    Machine Learning model for detecting fake job postings
    Supports multiple algorithms with TF-IDF vectorization
    Trained on real job posting dataset
    """

    def __init__(self, dataset_path='job_posts_dataset.csv', algorithm='knn'):
        """Initialize the ML model with dataset"""
        self.model = None
        self.vectorizer = None
        self.dataset_path = dataset_path
        self.training_data = None
        self.labels = None
        self.algorithm = algorithm
        self.training_metrics = None
        self.trained_at = None
        self._load_dataset()
        self._train_model(algorithm)
    
    def _load_dataset(self):
        """Load job posts dataset from CSV file"""
        try:
            # Check if dataset file exists
            if not os.path.exists(self.dataset_path):
                print(f"Warning: Dataset file '{self.dataset_path}' not found. Using default data.")
                self._create_default_data()
                return
            
            # Import pandas locally to avoid startup issues
            import pandas as pd
            
            # Load dataset from CSV
            df = pd.read_csv(self.dataset_path, encoding='utf-8')
            
            # Validate required columns
            required_columns = ['job_title', 'company_name', 'job_description', 'salary', 'label']
            if not all(col in df.columns for col in required_columns):
                raise ValueError(f"Dataset must contain columns: {required_columns}")
            
            # Combine text features
            df['combined_text'] = (
                df['job_title'].fillna('') + ' ' +
                df['company_name'].fillna('') + ' ' +
                df['job_description'].fillna('') + ' ' +
                df['salary'].fillna('')
            )
            
            # Extract features and labels
            self.training_data = df['combined_text'].values
            self.labels = df['label'].values
            
            print(f"[OK] Dataset loaded successfully: {len(self.training_data)} samples")
            print(f"  - Fake postings: {sum(self.labels == 1)}")
            print(f"  - Legitimate postings: {sum(self.labels == 0)}")
            
        except Exception as e:
            print(f"Error loading dataset: {str(e)}")
            self._create_default_data()
    
    def _create_default_data(self):
        """Create default training data if dataset not available"""
        # Import numpy locally to avoid startup issues
        import numpy as np
        
        training_texts = [
            "Send money to apply",
            "Work from home easy money",
            "No experience needed high pay",
            "Click here to register",
            "Urgent hiring immediate",
            "Free training provided jobs",
            "Make money fast online",
            "Investment required employment",
            "Guaranteed income opportunity",
            "Limited time offer job",
            # Legitimate posts
            "Software Engineer Full Stack Developer Position",
            "We are hiring experienced Python developers for our team",
            "Marketing Manager position at growing tech company",
            "Data Scientist role with competitive salary",
            "Customer Service Representative opportunity",
            "Project Manager needed for enterprise clients",
            "Business Development Executive opening",
            "Quality Assurance Engineer required"
        ]
        
        self.training_data = np.array(training_texts)
        self.labels = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
        print("[OK] Using default training data (18 samples)")
    
    def _train_model(self, algorithm='knn'):
        """Train the ML model using specified algorithm"""
        if self.training_data is None or self.labels is None:
            print("Error: No training data available")
            return
        
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.neighbors import KNeighborsClassifier
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.linear_model import LogisticRegression
            from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score
            from sklearn.model_selection import train_test_split
            
            # Split data into training (80%) and test (20%) sets
            X_train_text, X_test_text, y_train, y_test = train_test_split(
                self.training_data, self.labels, test_size=0.2, random_state=42, stratify=self.labels
            )
            
            # Create TF-IDF vectorizer and fit on training data only
            self.vectorizer = TfidfVectorizer(
                max_features=200,
                stop_words='english',
                lowercase=True,
                ngram_range=(1, 2),
                min_df=1,
                max_df=0.9
            )
            
            # Fit vectorizer on training texts and transform both sets
            X_train = self.vectorizer.fit_transform(X_train_text)
            X_test = self.vectorizer.transform(X_test_text)
            
            # Create model based on algorithm selection
            if algorithm == 'random_forest':
                self.model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
            elif algorithm == 'logistic_regression':
                self.model = LogisticRegression(max_iter=1000, random_state=42)
            else:  # Default to KNN
                self.model = KNeighborsClassifier(n_neighbors=5, weights='distance', algorithm='auto')
            
            # Train the model on training set
            self.model.fit(X_train, y_train)
            self.algorithm = algorithm
            self.trained_at = datetime.now().isoformat()
            
            # Calculate metrics on TEST set (unseen data)
            y_pred = self.model.predict(X_test)
            cm = confusion_matrix(y_test, y_pred)
            
            self.training_metrics = {
                'algorithm': algorithm,
                'accuracy': float(accuracy_score(y_test, y_pred)),
                'precision': float(precision_score(y_test, y_pred, zero_division=0)),
                'recall': float(recall_score(y_test, y_pred, zero_division=0)),
                'f1_score': float(f1_score(y_test, y_pred, zero_division=0)),
                'confusion_matrix': cm.tolist(),
                'training_samples': len(self.training_data),
                'features': X_train.shape[1],
                'trained_at': self.trained_at
            }
            
            print(f"[OK] Model trained successfully with {algorithm.upper()}")
            print(f"  - Accuracy: {self.training_metrics['accuracy']:.2%}")
            print(f"  - Precision: {self.training_metrics['precision']:.2%}")
            print(f"  - Recall: {self.training_metrics['recall']:.2%}")
            print(f"  - F1 Score: {self.training_metrics['f1_score']:.2%}")
            print(f"  - Features: {X_train.shape[1]}")
            print(f"  - Training samples used: {len(X_train_text)}")
            
        except Exception as e:
            print(f"Error training model: {str(e)}")
    
    def predict(self, job_description, job_title, company_name, salary):
        """
        Predict if a job post is fake or legitimate
        
        Args:
            job_description (str): The job post description
            job_title (str): Job position title
            company_name (str): Company name from the posting
            salary (str): Salary information
        
        Returns:
            dict: Prediction results with confidence scores
        """
        try:
            # Combine all text features
            combined_text = f"{job_title} {company_name} {job_description} {salary}"
            
            # Validate input
            if not combined_text.strip():
                return {
                    'error': 'Job post content is empty',
                    'is_fake': None,
                    'confidence': 0.0,
                    'fake_probability': 0.0,
                    'legitimate_probability': 0.0
                }
            
            # Vectorize the input
            X = self.vectorizer.transform([combined_text])
            
            # Make prediction
            prediction = self.model.predict(X)[0]
            probabilities = self.model.predict_proba(X)[0]
            
            # Calculate confidence (highest probability)
            confidence = max(probabilities) * 100
            
            # Get individual probabilities
            legitimate_prob = probabilities[0] * 100  # Class 0: Legitimate
            fake_prob = probabilities[1] * 100        # Class 1: Fake/Scam
            
            return {
                'is_fake': bool(prediction == 1),
                'confidence': float(confidence),
                'fake_probability': float(fake_prob),
                'legitimate_probability': float(legitimate_prob),
                'prediction_label': 'LIKELY SCAM' if prediction == 1 else 'APPEARS LEGITIMATE'
            }
        
        except Exception as e:
            return {
                'error': str(e),
                'is_fake': None,
                'confidence': 0.0,
                'fake_probability': 0.0,
                'legitimate_probability': 0.0
            }
    
    def get_model_info(self):
        """Get information about the ML model"""
        total_samples = len(self.labels) if self.labels is not None else 0
        fake_samples = int(sum(self.labels == 1)) if self.labels is not None else 0
        legitimate_samples = int(sum(self.labels == 0)) if self.labels is not None else 0
        
        return {
            'model_type': self.algorithm.replace('_', ' ').title() if self.algorithm else 'K-Neighbors Classifier',
            'vectorizer_type': 'TF-IDF',
            'features': 200,
            'training_samples': int(total_samples),
            'fake_samples': fake_samples,
            'legitimate_samples': legitimate_samples,
            'data_source': 'job_posts_dataset.csv',
            'trained_at': self.trained_at
        }
    
    def get_training_metrics(self):
        """Get detailed training metrics including confusion matrix"""
        return self.training_metrics if self.training_metrics else {}


# Initialize the detector
detector = FakeJobPostDetector()


def process_job_post(job_description, job_title, company_name, salary=""):
    """
    Process a job post and return prediction results
    
    Args:
        job_description (str): The job description text
        job_title (str): Job title
        company_name (str): Company name
        salary (str): Salary information
    
    Returns:
        dict: Prediction results from the ML model
    """
    result = detector.predict(job_description, job_title, company_name, salary)
    return result


def get_detector_info():
    """Get information about the detector model"""
    return detector.get_model_info()


def retrain_model(csv_file_path, algorithm='knn'):
    """
    Retrain the model with a new CSV file
    
    Args:
        csv_file_path (str): Path to the CSV file for training
        algorithm (str): Algorithm to use ('knn', 'random_forest', 'logistic_regression')
    
    Returns:
        dict: Result of the retraining operation with metrics
    """
    global detector
    
    try:
        # Create a new detector instance with the specified dataset and algorithm
        new_detector = FakeJobPostDetector(dataset_path=csv_file_path, algorithm=algorithm)
        
        # Check if model was successfully trained
        if new_detector.model is None or new_detector.vectorizer is None:
            return {
                'success': False,
                'message': 'Failed to train model. Please check the dataset format.'
            }
        
        # Replace the global detector with the newly trained one
        detector = new_detector
        
        model_info = detector.get_model_info()
        metrics = detector.get_training_metrics()
        
        return {
            'success': True,
            'message': f'Model successfully retrained with {model_info["training_samples"]} samples using {algorithm.upper()}',
            'model_info': model_info,
            'metrics': metrics
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'Error retraining model: {str(e)}'
        }
