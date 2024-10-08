import json
import pathlib
from typing import Union
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt

class QuestionnaireAnalysis:
    """
    Reads and analyzes data generated by the questionnaire experiment.
    Should be able to accept strings and pathlib.Path objects.
    """

    def __init__(self, data_fname: Union[pathlib.Path, str]):
        if isinstance(data_fname, str):
            data_fname = pathlib.Path(data_fname)
        if not data_fname.exists():
            raise ValueError(f"File {data_fname} does not exist.")
        self.data_fname = data_fname
        self.data = None

    def read_data(self):
        """
        Reads the json data located in self.data_fname into memory,
        to the attribute self.data.
        """
        with open(self.data_fname, 'r') as file:
            self.data = pd.DataFrame(json.load(file))

    def clean_data(self, data):
        """
        Cleans the given data by removing or correcting invalid entries.

        Parameters
        ----------
        data : pd.DataFrame or dict
            The data to clean. If a dictionary is provided, it will be converted to a DataFrame.

        Returns
        -------
        pd.DataFrame
            The cleaned DataFrame.
        """
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame(data)
        
        df = data.copy()  # Work on a copy to avoid modifying the original data

        # Convert 'age' to numeric, replacing non-numeric values with NaN
        df['age'] = pd.to_numeric(df['age'], errors='coerce')
        df = df[(df['age'] >= 0) & (df['age'].notna())]

        # Convert 'timestamp' to datetime, filter out invalid future dates
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df[df['timestamp'] <= datetime.now()]

        # Clean 'email' addresses
        df['email'] = df['email'].apply(lambda x: x if isinstance(x, str) and '@' in x and '.' in x.split('@')[-1] else np.nan)
        df = df.dropna(subset=['email'])

        # Convert 'gender' to a standardized set of values
        valid_genders = ['Male', 'Female', 'Other', 'Fluid']
        df['gender'] = df['gender'].apply(lambda x: x if x in valid_genders else np.nan)
        df = df.dropna(subset=['gender'])

        # Convert 'q1' to 'q5' to numeric, replace non-numeric values with NaN
        for col in ['q1', 'q2', 'q3', 'q4', 'q5']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    ########################-Q1-#########################

    def show_age_distrib(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Calculates and plots the age distribution of the participants.

        Returns
        -------
        hist : np.ndarray
            Number of people in a given bin
        bins : np.ndarray
            Bin edges
        """
        
        if self.data is None:
            raise ValueError("Data not loaded. Call read_data() before analysis.")
            
        bins = np.arange(0, 101, 10)
        ages = pd.to_numeric(self.data['age'], errors='coerce').dropna().astype(int).values
        hist, edges = np.histogram(ages, bins=bins)
        
        '''
        # Make this into a comment as we don't need to present this every time

        plt.figure()  # Explicitly create a figure
        plt.hist(ages, bins=bins, edgecolor='black')
        plt.title('Age Distribution')
        plt.xlabel('Age')
        plt.ylabel('Frequency')
        plt.grid(True)
        plt.show() 
        '''
        
        return hist, edges

    ########################-Q2-#########################

    def remove_rows_without_mail(self) -> pd.DataFrame:
        """
        Checks self.data for rows with invalid emails, and removes them.
        """
        if not isinstance(self.data, pd.DataFrame):
            raise TypeError("Data should be a pandas DataFrame")

        def is_valid_email(email):
            if pd.isna(email):
                return False
            parts = email.split('@')
            if len(parts) != 2:
                return False
            domain = parts[1]
            return '.' in domain and not email.startswith('.') and not email.endswith('.') and domain[0] != '.'

        df = self.data[self.data['email'].apply(is_valid_email)]
        df.reset_index(drop=True, inplace=True)
        return df

    ########################-Q3-#########################

    def fill_na_with_mean(self) -> tuple[pd.DataFrame, np.ndarray]:
        """
        Finds, in the original DataFrame, the subjects that didn't answer
        all questions, and replaces that missing value with the mean of the
        other grades for that student.

        Returns
        -------
        df : pd.DataFrame
            The corrected DataFrame after insertion of the mean grade
        arr : np.ndarray
            Row indices of the students that their new grades were generated
        """
        if self.data is None:
            raise ValueError("Data not loaded. Call read_data() before analysis.")
        
        # Ensure all relevant columns are numeric
        question_cols = ['q1', 'q2', 'q3', 'q4', 'q5']
        for col in question_cols:
            self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
        
        # Identify rows with missing values in question columns
        missing_values = self.data[question_cols].isna()
        rows_with_missing = missing_values.any(axis=1)

        # Compute means for rows with missing values
        means = self.data[question_cols].apply(lambda row: row.mean(), axis=1)
        filled_df = self.data.copy()

        # Fill missing values with computed means
        for i, row in filled_df.loc[rows_with_missing].iterrows():
            filled_df.loc[i, question_cols] = row[question_cols].fillna(means[i])
        
        # Get the indices of rows with missing values
        rows = self.data.index[rows_with_missing].to_numpy()
        
        return filled_df, rows

       ########################-Q4-#########################

    def score_subjects(self, maximal_nans_per_sub: int = 1) -> pd.DataFrame:
        """
        Calculates the average score of a subject and adds a new "score" column
        with it.

        If the subject has more than "maximal_nans_per_sub" NaN in his grades, the
        score should be NA. Otherwise, the score is simply the mean of the other grades.
        The datatype of score is UInt8, and the floating point raw numbers should be
        rounded down.

        Parameters
        ----------
        maximal_nans_per_sub : int, optional
            Number of allowed NaNs per subject before giving a NA score.

        Returns
        -------
        pd.DataFrame
            A new DF with a new column - "score".
        """
        if self.data is None:
            raise ValueError("Data not loaded. Call read_data() before analysis.")
    
        question_columns = ['q1', 'q2', 'q3', 'q4', 'q5']
        
        # Ensure all relevant columns are numeric
        self.data[question_columns] = self.data[question_columns].apply(pd.to_numeric, errors='coerce')
        
        # Calculate the mean score, ignoring NaNs
        score = self.data[question_columns].mean(axis=1)
        
        # Count NaNs in each row
        nan_counts = self.data[question_columns].isna().sum(axis=1)
        
        # Round down the scores and convert them to UInt8
        self.data['score'] = score.astype("uint8").astype("UInt8")
        
        # Set the score to NA where there are too many NaNs
        self.data.loc[nan_counts > maximal_nans_per_sub, 'score'] = pd.NA
        
        return self.data

    ########################-Q5-#########################

    def correlate_gender_age(self) -> pd.DataFrame:
        """Looks for a correlation between the gender of the subject, their age
        and the score for all five questions.

        Returns
        -------
        pd.DataFrame
            A DataFrame with a MultiIndex containing the gender and whether the subject is above
            40 years of age, and the average score in each of the five questions.
        """
        if self.data is None:
            raise ValueError("Data not loaded. Call read_data() before analysis.")
    
        # Ensure all relevant columns are numeric
        question_columns = ['q1', 'q2', 'q3', 'q4', 'q5']
        self.data[question_columns] = self.data[question_columns].apply(pd.to_numeric, errors='coerce')
        
        # Convert 'age' to numeric, replacing non-numeric values with NaN
        self.data['age'] = pd.to_numeric(self.data['age'], errors='coerce')
        
        # Remove rows where 'age' is NaN
        cleaned_data = self.data.dropna(subset=['age'])
        
        # Set MultiIndex with gender and age category (True if age > 40, else False)
        cleaned_data.set_index(['gender', cleaned_data['age'] > 40], inplace=True)
        
        # Group by gender and age category, and calculate the mean for each question
        grouped = cleaned_data.groupby(level=['gender', 'age'])[question_columns].mean()
        
        # Rename the MultiIndex level 'age' for clarity
        grouped.index.set_names(['gender', 'age'], inplace=True)
        
        return grouped
