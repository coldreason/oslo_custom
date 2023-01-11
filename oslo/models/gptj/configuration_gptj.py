# coding=utf-8
# Copyright 2021 TUNiB Inc.
# Copyright 2021 The EleutherAI and HuggingFace Teams. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" GPT-J model configuration """
from torch import nn
from transformers.configuration_utils import PretrainedConfig
from transformers.utils import logging

from oslo import (
    ColumnParallelLinear,
    RowParallelLinear,
    VocabParallelEmbedding,
)
from oslo.parallelism.mpu import Layer, LayerPolicy

logger = logging.get_logger(__name__)

GPTJ_PRETRAINED_CONFIG_ARCHIVE_MAP = {
    "EleutherAI/gpt-j-6B": "https://huggingface.co/EleutherAI/gpt-j-6B/resolve/main/config.json",
    # See all GPT-J models at https://huggingface.co/models?filter=gpt_j
}


class GPTJConfig(PretrainedConfig):
    r"""
    This is the configuration class to store the configuration of a :class:`~transformers.GPTJModel`. It is used to
    instantiate a GPT-J model according to the specified arguments, defining the model architecture. Instantiating a
    configuration with the defaults will yield a similar configuration to that of the GPT-J `gpt-j-6B
    <https://huggingface.co/EleutherAI/gpt-j-6B>`__ architecture. Configuration objects inherit from
    :class:`~transformers.PretrainedConfig` and can be used to control the model outputs. Read the documentation from
    :class:`~transformers.PretrainedConfig` for more information.

    Args:
        vocab_size (:obj:`int`, `optional`, defaults to 50400):
            Vocabulary size of the GPT-J model. Defines the number of different tokens that can be represented by the
            :obj:`inputs_ids` passed when calling :class:`~transformers.GPTJModel`.
        n_positions (:obj:`int`, `optional`, defaults to 2048):
            The maximum sequence length that this model might ever be used with. Typically set this to something large
            just in case (e.g., 512 or 1024 or 2048).
        n_embd (:obj:`int`, `optional`, defaults to 4096):
            Dimensionality of the embeddings and hidden states.
        n_layer (:obj:`int`, `optional`, defaults to 28):
            Number of hidden layers in the Transformer encoder.
        n_head (:obj:`int`, `optional`, defaults to 16):
            Number of attention heads for each attention layer in the Transformer encoder.
        rotary_dim (:obj:`int`, `optional`, defaults to 64):
            Number of dimensions in the embedding that Rotary Position Embedding is applied to.
        n_inner (:obj:`int`, `optional`, defaults to None):
            Dimensionality of the inner feed-forward layers. :obj:`None` will set it to 4 times n_embd
        activation_function (:obj:`str`, `optional`, defaults to :obj:`"gelu_new"`):
            Activation function, to be selected in the list :obj:`["relu", "silu", "gelu", "tanh", "gelu_new"]`.
        resid_pdrop (:obj:`float`, `optional`, defaults to 0.1):
            The dropout probability for all fully connected layers in the embeddings, encoder, and pooler.
        embd_pdrop (:obj:`int`, `optional`, defaults to 0.1):
            The dropout ratio for the embeddings.
        attn_pdrop (:obj:`float`, `optional`, defaults to 0.1):
            The dropout ratio for the attention.
        layer_norm_epsilon (:obj:`float`, `optional`, defaults to 1e-5):
            The epsilon to use in the layer normalization layers.
        initializer_range (:obj:`float`, `optional`, defaults to 0.02):
            The standard deviation of the truncated_normal_initializer for initializing all weight matrices.
        scale_attn_weights (:obj:`bool`, `optional`, defaults to :obj:`True`):
            Scale attention weights by dividing by sqrt(hidden_size).
        use_cache (:obj:`bool`, `optional`, defaults to :obj:`True`):
            Whether or not the model should return the last key/values attentions (not used by all models).

    Example::

        >>> from transformers import GPTJModel, GPTJConfig

        >>> # Initializing a GPT-J 6B configuration
        >>> configuration = GPTJConfig()

        >>> # Initializing a model from the configuration
        >>> model = GPTJModel(configuration)

        >>> # Accessing the model configuration
        >>> configuration = model.config
    """
    model_type = "gptj"
    attribute_map = {
        "max_position_embeddings": "n_positions",
        "hidden_size": "n_embd",
        "num_attention_heads": "n_head",
        "num_hidden_layers": "n_layer",
    }

    def __init__(
        self,
        vocab_size=50400,
        n_positions=2048,
        n_embd=4096,
        n_layer=28,
        n_head=16,
        rotary_dim=64,
        n_inner=None,
        activation_function="gelu_new",
        resid_pdrop=0.0,
        embd_pdrop=0.0,
        attn_pdrop=0.0,
        layer_norm_epsilon=1e-5,
        initializer_range=0.02,
        scale_attn_weights=True,
        use_cache=True,
        bos_token_id=50256,
        eos_token_id=50256,
        tie_word_embeddings=False,
        **kwargs
    ):
        self.vocab_size = vocab_size
        self.n_positions = n_positions
        self.n_embd = n_embd
        self.n_layer = n_layer
        self.n_head = n_head
        self.n_inner = n_inner
        self.rotary_dim = rotary_dim
        self.activation_function = activation_function
        self.resid_pdrop = resid_pdrop
        self.embd_pdrop = embd_pdrop
        self.attn_pdrop = attn_pdrop
        self.layer_norm_epsilon = layer_norm_epsilon
        self.initializer_range = initializer_range
        self.scale_attn_weights = scale_attn_weights
        self.use_cache = use_cache

        self.bos_token_id = bos_token_id
        self.eos_token_id = eos_token_id

        super().__init__(
            bos_token_id=bos_token_id,
            eos_token_id=eos_token_id,
            tie_word_embeddings=tie_word_embeddings,
            **kwargs
        )


class GPTJLayerPolicy(LayerPolicy):
    @staticmethod
    def reduce_arguments(layer, world_size, config):
        layer.attn.embed_dim = config.hidden_size // world_size
        layer.attn.num_attention_heads = config.n_head // world_size

    @staticmethod
    def fused_modules():
        from oslo.models.gptj.modeling_gptj import (
            GPTJMLP,
            FusedGPTJAttention,
            FusedGPTJMLP,
            GPTJAttention,
        )

        return {
            GPTJAttention: FusedGPTJAttention,
            GPTJMLP: FusedGPTJMLP,
        }

    @staticmethod
    def attn_qkv(layer, config):
        return [
            Layer(
                module=layer.attn.q_proj,
                weight=layer.attn.q_proj.weight,
                replace={nn.Linear: ColumnParallelLinear},
            ),
            Layer(
                module=layer.attn.k_proj,
                weight=layer.attn.k_proj.weight,
                replace={nn.Linear: ColumnParallelLinear},
            ),
            Layer(
                module=layer.attn.v_proj,
                weight=layer.attn.v_proj.weight,
                replace={nn.Linear: ColumnParallelLinear},
            ),
        ]

    @staticmethod
    def attn_out(layer, config):
        return [
            Layer(
                module=layer.attn.out_proj,
                weight=layer.attn.out_proj.weight,
                replace={nn.Linear: RowParallelLinear},
            ),
        ]

    @staticmethod
    def attn_norm(layer, config):
        return [
            Layer(
                module=layer.ln_1,
                weight=layer.ln_1.weight,
                bias=layer.ln_1.bias,
                parallel=False,
            ),
        ]

    @staticmethod
    def mlp_in(layer, config):
        return [
            Layer(
                module=layer.mlp.fc_in,
                weight=layer.mlp.fc_in.weight,
                bias=layer.mlp.fc_in.bias,
                replace={nn.Linear: ColumnParallelLinear},
            )
        ]

    @staticmethod
    def mlp_out(layer, config):
        return [
            Layer(
                module=layer.mlp.fc_out,
                weight=layer.mlp.fc_out.weight,
                bias=layer.mlp.fc_out.bias,
                replace={nn.Linear: RowParallelLinear},
            )
        ]

    @staticmethod
    def word_embedding(model, config):
        return [
            Layer(
                module=model.wte,
                weight=model.wte.weight,
                replace={nn.Embedding: VocabParallelEmbedding},
            ),
        ]

    @staticmethod
    def block_layers(model, config):
        return model.h

    @staticmethod
    def postblock_layers(model, config):
        return [
            Layer(
                module=model.ln_f,
                weight=model.ln_f.weight,
                bias=model.ln_f.bias,
                parallel=False,
            ),
        ]

    @staticmethod
    def copy_to_all(layer, config):
        return [
            Layer(
                bias=layer.attn.bias,
                parallel=False,
            ),
            Layer(
                bias=layer.attn.masked_bias,
                parallel=False,
            ),
        ]

    @staticmethod
    def original_layer_class():
        from oslo.models.gptj.modeling_gptj import GPTJBlock

        return GPTJBlock
