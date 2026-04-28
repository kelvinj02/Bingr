import pickle
import numpy as np
import pandas as pd


class MovieRecommender:
    def __init__(self, data_path: str, similarity_path: str):
        with open(data_path, "rb") as f:
            self.df = pickle.load(f)
        with open(similarity_path, "rb") as f:
            self.similarity = pickle.load(f)
        self.title_to_idx = pd.Series(
            self.df.index, index=self.df["title"]
        ).drop_duplicates()

    # ── public API ────────────────────────────────────────────────────────────

    def get_popular(self, top_n: int = 20, exclude: set = None) -> list:
        exclude = exclude or set()
        candidates = self.df[~self.df["title"].isin(exclude)]
        return self._format(candidates.head(top_n))

    def get_similar(self, title: str, top_n: int = 10) -> list:
        if title not in self.title_to_idx:
            return []
        idx = self.title_to_idx[title]
        scores = list(enumerate(self.similarity[idx]))
        scores = sorted(scores, key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in scores if self.df.iloc[i]["title"] != title][:top_n]
        return self._format(self.df.iloc[top_indices])

    def get_personalized(self, interactions: list, top_n: int = 20) -> list:
        interacted = {item["title"] for item in interactions}
        valid = [
            item["title"] for item in interactions
            if item["title"] in self.title_to_idx
        ]
        if not valid:
            return self.get_popular(top_n, exclude=interacted)

        indices = [self.title_to_idx[t] for t in valid]
        avg_scores = np.mean(self.similarity[indices], axis=0)

        candidates = self.df.copy()
        candidates["_score"] = avg_scores
        candidates = candidates[~candidates["title"].isin(interacted)]
        candidates = candidates.sort_values("_score", ascending=False).head(top_n)
        return self._format(candidates)

    # ── private helpers ───────────────────────────────────────────────────────

    def _format(self, df_slice: pd.DataFrame) -> list:
        results = []
        for _, row in df_slice.iterrows():
            results.append({
                "title":    row["title"],
                "movie_id": int(row["movie_id"]),
                "overview": row["overview"],
            })
        return results
