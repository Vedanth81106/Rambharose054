from twin.schemas import MLPrediction


class MLPredictor:

    def predict(
        self,
        telemetry_window: list[dict],
    ) -> MLPrediction:
        raise NotImplementedError