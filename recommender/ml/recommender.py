import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

RATING_WEIGHTS = {1: 0.0, 2: 0.1, 3: 0.5, 4: 1.0, 5: 1.5}
SAVED_WEIGHT = 0.75
READ_WEIGHT = 0.5
QUALITY_WEIGHTS = (0.7, 0.3)        # (norm_avg_rating, norm_log_ratings)
PERSONALIZED_MIX = (0.75, 0.25)     # (cosine_sim, quality_score)
SIMILAR_DEFAULT_QUALITY = 0.15
MIN_INTERACTIONS_FULL_PROFILE = 3


class BookRecommender:
    def __init__(self, csv_path: str):
        df = pd.read_csv(csv_path)
        df = df[["Book", "Author", "Description", "Genres", "Avg_Rating", "Num_Ratings", "URL"]].copy()

        df["Book"] = df["Book"].fillna("")
        df["Author"] = df["Author"].fillna("")
        df["Description"] = df["Description"].fillna("")
        df["Genres"] = df["Genres"].fillna("")
        df["URL"] = df["URL"].fillna("")

        df["Avg_Rating"] = pd.to_numeric(df["Avg_Rating"], errors="coerce").fillna(0)
        df["Num_Ratings"] = (
            df["Num_Ratings"].astype(str).str.replace(",", "", regex=False)
        )
        df["Num_Ratings"] = pd.to_numeric(df["Num_Ratings"], errors="coerce").fillna(0)

        df["Genres_Clean"] = df["Genres"].apply(self._clean_genres)
        genre_split = df["Genres_Clean"].str.split(",", n=3, expand=True)
        df["Genre1"] = genre_split[0].fillna("").str.strip()
        df["Genre2"] = genre_split[1].fillna("").str.strip() if 1 in genre_split.columns else ""
        df["Genre3"] = genre_split[2].fillna("").str.strip() if 2 in genre_split.columns else ""
        df["Genre4"] = genre_split[3].fillna("").str.strip() if 3 in genre_split.columns else ""

        df["cleaned_desc"] = df["Description"].apply(self._clean_text)

        df = df[
            (df["Book"].str.strip() != "") &
            (df["cleaned_desc"].str.strip() != "") &
            (df["Genre1"].str.strip() != "") &
            (df["Avg_Rating"] > 0) &
            (df["Num_Ratings"] > 50)
        ].copy()
        df = df.sort_values("Num_Ratings", ascending=False).head(10000).reset_index(drop=True)

        df["rating_score"] = df["Avg_Rating"] / df["Avg_Rating"].max()
        log_ratings = np.log1p(df["Num_Ratings"])
        df["popularity_score"] = log_ratings / log_ratings.max()
        df["quality_score"] = (
            QUALITY_WEIGHTS[0] * df["rating_score"] +
            QUALITY_WEIGHTS[1] * df["popularity_score"]
        )

        df["combined_features"] = (
            df["Genre1"].astype(str) + " " +
            df["Genre2"].astype(str) + " " +
            df["Genre3"].astype(str) + " " +
            df["Genre4"].astype(str) + " " +
            df["Author"].astype(str) + " " +
            df["cleaned_desc"].astype(str)
        )

        tfidf = TfidfVectorizer(stop_words="english", max_features=10000)
        self.tfidf_matrix = tfidf.fit_transform(df["combined_features"])
        self.quality_scores = df["quality_score"].values
        _s = pd.Series(df.index, index=df["Book"])
        self.title_to_idx = _s[~_s.index.duplicated(keep='first')]
        self.df = df

        all_genres = set()
        for g in df["Genres_Clean"]:
            for part in g.split(","):
                part = part.strip()
                if part:
                    all_genres.add(part)
        self.genres = sorted(all_genres)

    # ── public API ────────────────────────────────────────────────────────────

    def get_cold_start(self, genres: list, top_n: int = 20, exclude: set = None) -> list:
        exclude = exclude or set()
        if genres:
            mask = self.df[["Genre1", "Genre2", "Genre3", "Genre4"]].apply(
                lambda row: any(
                    g.lower() in (cell.lower() for cell in row if cell)
                    for g in genres
                ),
                axis=1,
            )
            candidates = self.df[mask].copy()
        else:
            candidates = self.df.copy()

        candidates = candidates[~candidates["Book"].isin(exclude)]
        candidates = candidates.sort_values("quality_score", ascending=False)
        # Fetch a large pool first, then diversify to avoid one author dominating
        pool = self._format_results(candidates.head(top_n * 5))
        return self._diversify(pool, top_n, max_per_author=2)

    def get_personalized(self, interactions: list, genres: list, top_n: int = 20) -> list:
        exclude = {i["title"] for i in interactions}
        if not interactions:
            return self.get_cold_start(genres, top_n, exclude)
        if len(interactions) < MIN_INTERACTIONS_FULL_PROFILE:
            return self._sparse_recommendations(interactions, genres, top_n, exclude)
        return self._profile_recommendations(interactions, top_n, exclude)

    def get_similar(self, title: str, top_n: int = 5, exclude: set = None,
                    quality_weight: float = SIMILAR_DEFAULT_QUALITY) -> list:
        exclude = exclude or set()
        if title not in self.title_to_idx:
            return []
        n = len(self.quality_scores)
        idx = self.title_to_idx[title]
        sim_scores = cosine_similarity(self.tfidf_matrix[idx], self.tfidf_matrix[:n]).flatten()
        combined = (1 - quality_weight) * sim_scores + quality_weight * self.quality_scores
        candidates = self.df.copy()
        candidates["_score"] = combined
        candidates = candidates[~candidates["Book"].isin(exclude)]
        candidates = candidates[candidates["Book"] != title]
        candidates = candidates.sort_values("_score", ascending=False).head(top_n)
        return self._format_results(candidates, score_col="_score")

    # ── private helpers ───────────────────────────────────────────────────────

    def _profile_recommendations(self, interactions: list, top_n: int, exclude: set) -> list:
        profile = self._build_profile_vector(interactions)
        if profile is None:
            return []
        n = len(self.quality_scores)
        sim_scores = cosine_similarity(profile, self.tfidf_matrix[:n]).flatten()
        combined = PERSONALIZED_MIX[0] * sim_scores + PERSONALIZED_MIX[1] * self.quality_scores
        candidates = self.df.copy()
        candidates["_score"] = combined
        candidates = candidates[~candidates["Book"].isin(exclude)]
        candidates = candidates.sort_values("_score", ascending=False).head(top_n)
        return self._format_results(candidates, score_col="_score")

    def _sparse_recommendations(self, interactions: list, genres: list,
                                 top_n: int, exclude: set) -> list:
        cold = self.get_cold_start(genres, top_n * 3, exclude)
        profile = self._build_profile_vector(interactions)
        if profile is None:
            return cold[:top_n]

        n = len(self.quality_scores)
        sim_scores = cosine_similarity(profile, self.tfidf_matrix[:n]).flatten()
        candidates = self.df.copy()
        candidates["_sim"] = sim_scores
        candidates = candidates[~candidates["Book"].isin(exclude)]

        max_cold = max((b["score"] for b in cold), default=1) or 1
        max_sim = candidates["_sim"].max() or 1

        results = {}
        for b in cold:
            results[b["title"]] = {**b, "_cold": b["score"] / max_cold, "_sim": 0.0}

        for _, row in candidates.iterrows():
            t = row["Book"]
            norm_sim = row["_sim"] / max_sim
            if t in results:
                results[t]["_sim"] = norm_sim
            else:
                results[t] = {
                    "title": t,
                    "author": row["Author"],
                    "genres": row["Genres_Clean"],
                    "avg_rating": row["Avg_Rating"],
                    "num_ratings": int(row["Num_Ratings"]),
                    "url": row["URL"],
                    "_cold": 0.0,
                    "_sim": norm_sim,
                }

        for r in results.values():
            r["score"] = round(0.5 * r.pop("_cold") + 0.5 * r.pop("_sim"), 4)

        return sorted(results.values(), key=lambda x: x["score"], reverse=True)[:top_n]

    def _build_profile_vector(self, interactions: list):
        vectors, weights = [], []
        for item in interactions:
            title = item.get("title", "")
            if title not in self.title_to_idx:
                continue
            rating = item.get("rating")
            status = item.get("status", "")
            if rating is not None:
                weight = RATING_WEIGHTS.get(int(rating), 0.0)
            elif status == "saved":
                weight = SAVED_WEIGHT
            else:
                weight = READ_WEIGHT
            if weight == 0.0:
                continue
            idx = self.title_to_idx[title]
            vectors.append(self.tfidf_matrix[idx])
            weights.append(weight)

        if not vectors:
            return None
        weights = np.array(weights)
        weighted = sum(w * v for w, v in zip(weights, vectors))
        return weighted / weights.sum()

    def _diversify(self, results: list, top_n: int, max_per_author: int = 2) -> list:
        seen = {}
        diverse = []
        for book in results:
            author = book.get("author", "")
            if seen.get(author, 0) < max_per_author:
                diverse.append(book)
                seen[author] = seen.get(author, 0) + 1
            if len(diverse) >= top_n:
                break
        return diverse

    def _format_results(self, df_slice: pd.DataFrame, score_col: str = "quality_score") -> list:
        results = []
        for _, row in df_slice.iterrows():
            results.append({
                "title": row["Book"],
                "author": row["Author"],
                "genres": row["Genres_Clean"],
                "avg_rating": row["Avg_Rating"],
                "num_ratings": int(row["Num_Ratings"]),
                "url": row["URL"],
                "score": round(float(row[score_col]), 4),
            })
        return results

    @staticmethod
    def _clean_genres(text: str) -> str:
        text = str(text).replace("[", "").replace("]", "")
        text = text.replace("'", "").replace('"', "")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _clean_text(text: str) -> str:
        text = "".join(c for c in str(text) if ord(c) < 128)
        text = text.lower()
        text = re.sub(r"<.*?>", "", text)
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()
