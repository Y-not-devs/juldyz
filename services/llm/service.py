import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from pathlib import Path
from huggingface_hub import snapshot_download


class LLM_Service:
    """
    LLM_Service modes:
        0 = offline_only
        1 = auto_update
        2 = token_update
    """

    def __init__(self, db, model_path: str, hf_model_id: str, hf_token: str = None, mode: int = 1):
        self.db = db
        # self.logger = logger

        self.MODEL_PATH = Path(model_path)
        self.HF_MODEL_ID = hf_model_id
        self.HF_TOKEN = hf_token

        self.mode = mode

        self._model = None
        self._tokenizer = None

        if self.mode in (1, 2):
            self._download_model()

        self._load_model()

    def _download_model(self):
        try:
            # self.logger.info(f"Downloading model: {self.HF_MODEL_ID}")

            snapshot_download(
                repo_id=self.HF_MODEL_ID,
                local_dir=str(self.MODEL_PATH),
                local_dir_use_symlinks=False,
                token=self.HF_TOKEN if self.mode == 2 else None,
            )

            # self.logger.info("Model download completed.")

        except Exception as e:
            # self.logger.warning(f"Download failed. Falling back to local model. Error: {e}")
            pass

    def _load_model(self):
        if not self.MODEL_PATH.exists():
            raise FileNotFoundError(f"Model directory not found: {self.MODEL_PATH}")

        # self.logger.info(f"Loading model from: {self.MODEL_PATH}")

        use_cuda = torch.cuda.is_available()

        if use_cuda:
            # self.logger.info("CUDA detected. Loading 4-bit quantized model.")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
        else:
            # self.logger.info("CUDA not available. Loading model in full precision.")
            bnb_config = None
        print(self.MODEL_PATH)
        self._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_PATH)

        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        self._model = AutoModelForCausalLM.from_pretrained(
            self.MODEL_PATH,
            quantization_config=bnb_config,
            device_map="auto" if use_cuda else None,
            trust_remote_code=True,
            local_files_only=True,
        )

        if not use_cuda:
            self._model.to("cpu")

        # self.logger.info("Model loaded successfully.")

    def generate_response(
        self,
        prompt: str,
        max_new_tokens: int = 150,
        temperature: float = 0.7,
    ) -> str:

        if self._model is None or self._tokenizer is None:
            raise RuntimeError("Model is not loaded.")

        inputs = self._tokenizer(prompt, return_tensors="pt")
        input_length = inputs["input_ids"].shape[1]

        if torch.cuda.is_available():
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        # Decode only the newly generated tokens, not the prompt
        generated_tokens = outputs[0][input_length:]
        return self._tokenizer.decode(generated_tokens, skip_special_tokens=True)

if __name__ == "__main__":

    bot = LLM_Service(
        model_path="./models/qwen",
        hf_model_id="Qwen/Qwen2.5-1.5B-Instruct",
        mode=1,  # 0=offline, 1=auto_update, 2=token_update
        hf_token=None,
    )

    prompt = (
        "Ты медицинский ассистент. "
        "Задай уточняющий вопрос по симптомам: головная боль и слабость."
    )

    response = bot.generate_response(prompt)

    print("Generated response:")
    print(response)