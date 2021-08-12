import math
import hashlib

import numpy as np

from abc import abstractmethod
from nltk import word_tokenize

from .utilities import Word2Syllable
from .utilities import word2ngram
from .utilities import word2skipngram
from .utilities import LocalitySensitiveHashing


class BaseTokenizer:
    def __init__(self, 
                num_embeddings: int, 
                padding_idx: int=0):

        self.num_embeddings = num_embeddings
        self.padding_idx = padding_idx

    def __call__(self, inputs: list):
        return [[self.numerize(token) for token in self.tokenize(inp)] for inp in inputs]

    @abstractmethod
    def tokenize(self, inp):
        """ Convert a given input into a sequence of tokens """
        pass

    @abstractmethod
    def numerize(self, token):
        """ Convert a given token into a number """
        pass


class TextTokenizer(BaseTokenizer):
    special_tokens = ["<PAD>", "<CLS>", "<SEP>", "<MASK>", "<UNK>"]

    def __init__(self, 
                num_embeddings: int, 
                padding_idx: int=0,
                input_word: bool=False):

        super().__init__(num_embeddings, padding_idx)
        self.input_word = input_word


class HashingBasedTokenizer(TextTokenizer):
    def numerize(self, token: str):
        """ Convert a given token into a number """
        hash_number = int(hashlib.sha3_224(bytes(token, "utf8")).hexdigest(), 16) % self.num_embeddings
        hash_number = max(hash_number, self.padding_idx + len(self.special_tokens))
        return hash_number


class LocalitySensitiveHashingBasedTokenizer(TextTokenizer):
    def __init__(self, 
                 num_embeddings: int, 
                 padding_idx: int=0,
                 random_seed: int=0):

        super().__init__(num_embeddings, padding_idx)
        self.lsh = LocalitySensitiveHashing(num_embeddings, random_seed)

    def numerize(self, token: str):
        """ Convert a given token into a number """
        hash_number = self.lsh(token) % self.num_embeddings
        hash_number = max(hash_number, self.padding_idx + len(self.special_tokens))
        return hash_number


class WordTokenizer(HashingBasedTokenizer):
    def tokenize(self, string: str):
        """ Convert a given string into a sequence of tokens """
        return word_tokenize(string) if not self.input_word else [string]


class NgramLevelWordTokenizer(HashingBasedTokenizer):
    def __init__(self, 
                 num_embeddings: int, 
                 padding_idx: int=0,
                 ngrams: list=(3, 4, 5, 6),
                 skipngrams: list=(2, 3)):
        
        super().__init__(num_embeddings, padding_idx)
        self.ngrams = ngrams
        self.skipngrams = skipngrams

    def tokenize(self, string: str):
        """ Convert a given string into a sequence of tokens """
        words = word_tokenize(string) if not self.input_word else [string]
        tokens = []
        for word in words:
            grams = []
            for n in self.ngrams:
                grams.extend(word2ngram(word, n))
            for n in self.skipngrams:
                grams.extend(word2skipngram(word, n))
            tokens.append(grams)
        return tokens

    def numerize(self, grams: list[str]):
        """ Convert a given list of tokens into a list of numbers """
        sub = super()
        return [sub.numerize(gram) for gram in grams]


class LshNgramLevelWordTokenizer(LocalitySensitiveHashingBasedTokenizer):
    def __init__(self, 
                 num_embeddings: int, 
                 padding_idx: int=0,
                 random_seed: int=0,
                 ngrams: list=(3, 4, 5, 6),
                 skipngrams: list=(2, 3)):
        
        super().__init__(num_embeddings, padding_idx, random_seed)
        self.ngrams = ngrams
        self.skipngrams = skipngrams

    def tokenize(self, string: str):
        """ Convert a given string into a sequence of tokens """
        words = word_tokenize(string) if not self.input_word else [string]
        tokens = []
        for word in words:
            grams = []
            for n in self.ngrams:
                grams.extend(word2ngram(word, n))
            for n in self.skipngrams:
                grams.extend(word2skipngram(word, n))
            tokens.append(grams)
        return tokens

    def numerize(self, grams: list[str]):
        """ Convert a given list of tokens into a list of numbers """
        sub = super()
        return [sub.numerize(gram) for gram in grams]


class CharacterLevelWordTokenizer(HashingBasedTokenizer):
    def tokenize(self, string: str):
        """ Convert a given string into a sequence of tokens """
        words = word_tokenize(string) if not self.input_word else [string]
        tokens = [list(word) for word in words]
        return tokens

    def numerize(self, chars: list[str]):
        """ Convert a given list of tokens into a list of numbers """
        sub = super()
        return [sub.numerize(char) for char in chars]


class PositionalCharacterLevelWordTokenizer(HashingBasedTokenizer):
    def __init__(self, 
                num_embeddings: int,
                padding_idx: int=0,
                max_positional: int=10):

        super().__init__(num_embeddings, padding_idx)
        self.max_positional = max_positional

    def tokenize(self, string: str):
        """ Convert a given string into a sequence of tokens """
        words = word_tokenize(string) if not self.input_word else [string]
        tokens = [self.positionize(list(word)) for word in words]
        return tokens

    def numerize(self, token: list[str]):
        """ Convert a given list of tokens into a list of tuples of number and position """
        sub = super()
        chars, positions = token
        numbers = [sub.numerize(char) for char in chars]
        return numbers, positions

    @abstractmethod
    def positionize(self, chars: list[str]):
        pass


class RoughPositionalCharacterLevelWordTokenizer(PositionalCharacterLevelWordTokenizer):
    language_options = ["en", "th"]

    def __init__(self, 
                num_embeddings: int,
                padding_idx: int=0,
                max_positional: int=10,
                language: str="en"):
        assert language in self.language_options

        super().__init__(num_embeddings, padding_idx, max_positional)
        self.word2syllable = Word2Syllable(language)

    def positionize(self, chars: list[str]):
        syllables = self.word2syllable("".join(chars))
        positions = []
        for i, syllable in enumerate(syllables):
            for _ in syllable:
                positions.append(min(i, self.max_positional - 1))
        return chars, positions


class PrecisePositionalCharacterLevelWordTokenizer(PositionalCharacterLevelWordTokenizer):
    def positionize(self, chars: list[str]):
        positions = [min(i, self.max_positional - 1) for i in range(len(chars))]
        return chars, positions


class SignalTokenizer(BaseTokenizer):
    def __init__(self, 
                num_embeddings: int,
                padding_idx: int=0,
                window_size: int=1000,
                stride: int=100,
                padding_value: float=0.0,
                random_seed: int=0):

        super().__init__(num_embeddings, padding_idx)
        self.window_size = window_size
        self.stride = stride
        self.padding_value = padding_value

        np.random.seed(random_seed)
        self.random_vecs = np.random.normal(size=[math.ceil(math.log(num_embeddings, 2)), window_size])

    def __call__(self, signals: list[np.ndarray]):
        return [self.numerize(self.tokenizer(signal)) for signal in signals]

    def tokenizer(self, signal: np.ndarray):
        """
        signal: (signal_length, )
        return: (output_length, window_size)
        """
        signal_length = signal.shape[0]

        # Calculate padding size
        output_length = math.ceil((signal_length - self.window_size) / self.stride + 1)
        padding_size = (output_length - 1) * self.stride - signal_length + self.window_size
        # Padding
        signal = np.pad(signal, (0, padding_size), "constant", constant_values=self.padding_value)
        # Tokenize
        tokens = np.concatenate([signal[np.newaxis, i * self.stride:i * self.stride + self.window_size] for i in range(output_length)], axis=0)
        return tokens

    def numerize(self, tokens: np.ndarray):
        """
        tokens: (output_length, window_size)
        return: (output_length, )
        """
        binary_vecs = (tokens @ self.random_vecs.T > 0).astype(int)
        numbers = [int("".join([str(val) for val in vector]), 2) % self.num_embeddings for vector in binary_vecs]
        numbers = [max(number, self.padding_idx + 1) for number in numbers]
        return numbers


class SignalDerivativeTokenizer(SignalTokenizer):
    def tokenizer(self, signal: np.ndarray):
        """
        signal: (signal_length, )
        return: (output_length, window_size)
        """
        signal = signal[1:] - signal[:-1]
        signal_length = signal.shape[0]

        # Calculate padding size
        output_length = math.ceil((signal_length - self.window_size) / self.stride + 1)
        padding_size = (output_length - 1) * self.stride - signal_length + self.window_size
        # Padding
        signal = np.pad(signal, (0, padding_size), "constant", constant_values=self.padding_value)
        # Tokenize
        tokens = np.concatenate([signal[np.newaxis, i * self.stride:i * self.stride + self.window_size] for i in range(output_length)], axis=0)
        return tokens


class ImageTokenizer(BaseTokenizer):
    def __init__(self,
                 num_embeddings: int,
                 padding_idx: int=0,
                 window_height: int=9,
                 window_width: int=9,
                 stride: int=1,
                 padding_value: float=0,
                 random_seed: int=0):

        super().__init__(num_embeddings, padding_idx)
        self.window_height = window_height
        self.window_width = window_width
        self.stride = stride
        self.padding_value = padding_value

        np.random.seed(random_seed)
        self.random_vecs = np.random.normal(size=[math.ceil(math.log(num_embeddings, 2)), window_height * window_width])

    def __call__(self, images: list[np.ndarray]):
        return [self.numerize(self.tokenizer(image)) for image in images]

    def tokenizer(self, image: np.ndarray):
        """
        image: (height, width)
        return: (output_height, output_width, window_height, window_width)
        """
        height, width = image.shape

        # Calculate padding size
        output_height = math.ceil((height - self.window_height) / self.stride + 1)
        height_padding_size = (output_height - 1) * self.stride - height + self.window_height

        output_width = math.ceil((width - self.window_width) / self.stride + 1)
        width_padding_size = (output_width - 1) * self.stride - width + self.window_width

        # Padding
        image = np.pad(image, (height_padding_size, width_padding_size), "constant", constant_values=self.padding_value)

        # Tokenize
        tokens = np.empty([output_height, output_width, self.window_height, self.window_width])
        for i in range(output_height):
            for j in range(output_width):
                # Get start and end indices
                start_y = i * self.stride
                end_y = start_y + self.window_height
                start_x = i * self.stride
                end_x = start_x + self.window_width
                # Get token
                tokens[i, j] = image[start_y:end_y, start_x:end_x]
        return tokens

    def numerize(self, tokens: np.ndarray):
        """
        tokens: (output_height, output_width, window_height, window_width)
        return: (output_height, output_width)
        """
        # Reshape tokens
        output_height, output_width, _, _ = tokens.shape
        tokens = tokens.reshape(output_height, output_width, -1)

        # (output_height, output_width, log(num_embeddings, 2))
        binary_vecs = (tokens @ self.random_vecs.T > 0).astype(int)
        # numbers = np.zeros([output_height, output_width], dtype=int)
        numbers = np.apply_along_axis(lambda x: int("".join(x), 2) % self.num_embeddings, -1, binary_vecs)
        return numbers


class SpectrogramTokenizer(SignalTokenizer):
    def __init__(self, 
                num_embeddings: int,
                sampling_rate: int=22050,
                n_fft: int=2000,
                hop_length=100,
                window_size: int=9,
                stride: int=1,
                padding_value: float=-80,
                random_seed: int=0):

        super().__init__(num_embeddings, window_size, stride, padding_value, random_seed)
        self.sampling_rate = sampling_rate
        self.n_fft = n_fft
        self.hop_length = hop_length

        np.random.seed(random_seed)
        self.random_vecs = np.random.normal(size=[math.ceil(math.log(num_embeddings, 2)), window_size * window_size])

    def shorten_signal(signal, threshold=1e-3, offset=500):
        start_id = 0
        for i in np.arange(signal.shape[0]):
            value = signal[i]
            if abs(value) > threshold:
                start_id = i
                break

        end_id = math.inf
        for i in np.arange(signal.shape[0])[::-1]:
            value = signal[i]
            if abs(value) > threshold:
                end_id = i
                break
                
        signal = signal[start_id - offset:end_id + offset]
        return signal

    def tokenizer(self, signal: np.ndarray):
        """
        signal: (signal_length, )
        return: (output_length, window_size)
        """
        signal = self.shorten_signal(signal)
        signal_length = signal.shape[0]

        # Calculate padding size
        output_length = math.ceil((signal_length - self.window_size) / self.stride + 1)
        padding_size = (output_length - 1) * self.stride - signal_length + self.window_size
        # Padding
        signal = np.pad(signal, (0, padding_size), "constant", constant_values=self.padding_value)
        # Tokenize
        tokens = np.concatenate([signal[np.newaxis, i * self.stride:i * self.stride + self.window_size] for i in range(output_length)], axis=0)
        return tokens


# class _BaseTokenizer:
#     def __init__(self, 
#                 max_vocabs: int=None,
#                 min_freq: int=None,
#                 pad_to_length: Union[None, str, int]=None,
#                 truncate: bool=False,
#                 pad_token_id: int=0,
#                 cls_token_id: int=1,
#                 sep_token_id: int=2,
#                 mask_token_id: int=3,
#                 return_padding_mask: bool=False):

#         self.max_vocabs = max_vocabs
#         self.min_freq = min_freq
#         self.padding = TokenPadding(pad_to_length, truncate, pad_token_id, return_padding_mask)
#         self.pad_token_id = pad_token_id
#         self.cls_token_id = cls_token_id
#         self.sep_token_id = sep_token_id
#         self.mask_token_id = mask_token_id
#         self.vocabs = []
#         self.vocab2id = {}
#         self.id2vocab = {}

#     def __call__(self, texts: List[str], start_token=False, end_token=False) -> Dict:
#         token_ids = np.asarray([self.text2ids(text, start_token=start_token, end_token=end_token) for text in texts])
#         return self.padding(token_ids)

#     @abstractmethod
#     def tokenizer(self, text):
#         pass

#     def text2ids(self, text, start_token=False, end_token=False):
#         tokens = self.text2tokens(text, start_token=start_token, end_token=end_token)

#         token_ids = [self.vocab2id.get(token, self.unk_token_id) for token in tokens]
#         return token_ids

#     def text2tokens(self, text, start_token=False, end_token=False):
#         tokens = self.tokenizer(text)
#         if start_token:
#             tokens = [self.cls_token] + tokens
#         if end_token:
#             tokens = tokens + [self.sep_token]
#         return tokens

#     def ids2text(self, ids, remove_special_token=True):
#         tokens = self.ids2tokens(ids, remove_special_token=remove_special_token)
#         text = "".join(tokens)
#         return text

#     def ids2tokens(self, ids, remove_special_token=True):
#         tokens = []
#         for i in ids:
#             if remove_special_token and i in [self.pad_token_id, self.cls_token_id, self.sep_token_id, self.mask_token_id, self.unk_token_id]:
#                 continue
#             tokens.append(self.id2vocab[i])
#         return tokens

#     def save(self, save_dir):
#         with open(save_dir, "w") as f:
#             [f.write(vocab + "\n") for vocab in self.vocabs]

#     def load(self, load_dir):
#         with open(load_dir, "r") as f:
#             self.vocabs = f.read()[:-1].split("\n")
#             # Get vocab2id and id2vocab
#             self.vocab2id[self.pad_token] = self.pad_token_id
#             self.vocab2id[self.cls_token] = self.cls_token_id
#             self.vocab2id[self.sep_token] = self.sep_token_id
#             self.vocab2id[self.mask_token] = self.mask_token_id

#             self.vocab2id.update({token: i + len(self.vocab2id) for i, token in enumerate(self.vocabs)})

#             self.vocab2id[self.unk_token] = self.unk_token_id
#             self.id2vocab = {i: token for token, i in self.vocab2id.items()}

#     def fit(self, corpus: List, initial_vocabs: List=None):
#         # Get tokens frequency
#         token_freq = {}
#         for text in tqdm(corpus):
#             tokens = self.tokenizer(text)
#             for token in tokens:
#                 token_freq[token] = token_freq.get(token, 0) + 1

#         # Get vocabs
#         if self.max_vocabs is not None and self.min_freq is not None:
#             sorted_token_freq = sorted(token_freq.items(), key=lambda x: x[1], reverse=True)
#             self.vocabs = [token for token, freq in sorted_token_freq[:self.max_vocabs] if freq >= self.min_freq]
#         elif self.max_vocabs is not None:
#             sorted_token_freq = sorted(token_freq.items(), key=lambda x: x[1], reverse=True)
#             self.vocabs = [token for token, _ in sorted_token_freq[:self.max_vocabs]]
#         elif self.min_freq is not None:
#             self.vocabs = [token for token, freq in token_freq.items() if freq >= self.min_freq]
#         else:
#             self.vocabs = list(token_freq.keys())

#         # Get vocab2id and id2vocab
#         self.vocab2id[self.pad_token] = self.pad_token_id
#         self.vocab2id[self.cls_token] = self.cls_token_id
#         self.vocab2id[self.sep_token] = self.sep_token_id
#         self.vocab2id[self.mask_token] = self.mask_token_id

#         if initial_vocabs is not None:
#             self.vocabs = initial_vocabs + self.vocabs
#         self.vocab2id.update({token: i + len(self.vocab2id) for i, token in enumerate(self.vocabs)})

#         self.vocab2id[self.unk_token] = self.unk_token_id
#         self.id2vocab = {i: token for token, i in self.vocab2id.items()}

#     @property
#     def vocab_size(self):
#         return len(self.vocab2id)

#     @property
#     def pad_token(self):
#         return "<PAD>"

#     @property
#     def cls_token(self):
#         return "<CLS>"

#     @property
#     def sep_token(self):
#         return "<SEP>"

#     @property
#     def mask_token(self):
#         return "<MASK>"

#     @property
#     def unk_token(self):
#         return "<UNK>"

#     @property
#     def unk_token_id(self):
#         return len(self.vocabs) + 4