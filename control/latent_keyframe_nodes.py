from typing import Union
import numpy as np
from collections.abc import Iterable

from .control import LatentKeyframeImport, LatentKeyframeGroupImport
from .logger import logger


class LatentKeyframeNodeImport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "batch_index": ("INT", {"default": 0, "min": -1000, "max": 1000, "step": 1}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.00001}, ),
            },
            "optional": {
                "prev_latent_keyframe": ("LATENT_KEYFRAME", ),
            }
        }

    RETURN_TYPES = ("LATENT_KEYFRAME", )
    FUNCTION = "load_keyframe"

    CATEGORY = "Adv-ControlNet 🛂🅐🅒🅝/keyframes"

    def load_keyframe(self,
                      batch_index: int,
                      strength: float,
                      prev_latent_keyframe: LatentKeyframeGroupImport=None):
        if not prev_latent_keyframe:
            prev_latent_keyframe = LatentKeyframeGroupImport()
        keyframe = LatentKeyframeImport(batch_index, strength)
        prev_latent_keyframe.add(keyframe)
        return (prev_latent_keyframe,)


class LatentKeyframeGroupNodeImport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "index_strengths": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "prev_latent_keyframe": ("LATENT_KEYFRAME", ),
                "latent_optional": ("LATENT", ),
            }
        }
    
    RETURN_TYPES = ("LATENT_KEYFRAME", )
    FUNCTION = "load_keyframes"

    CATEGORY = "Adv-ControlNet 🛂🅐🅒🅝/keyframes"

    def validate_index(self, index: int, latent_count: int = 0, is_range: bool = False, allow_negative = False) -> int:
        # if part of range, do nothing
        if is_range:
            return index
        # otherwise, validate index
        # validate not out of range - only when latent_count is passed in
        if latent_count > 0 and index > latent_count-1:
            raise IndexError(f"Index '{index}' out of range for the total {latent_count} latents.")
        # if negative, validate not out of range
        if index < 0:
            if not allow_negative:
                raise IndexError(f"Negative indeces not allowed, but was {index}.")
            conv_index = latent_count+index
            if conv_index < 0:
                raise IndexError(f"Index '{index}', converted to '{conv_index}' out of range for the total {latent_count} latents.")
            index = conv_index
        return index

    def convert_to_index_int(self, raw_index: str, latent_count: int = 0, is_range: bool = False, allow_negative = False) -> int:
        try:
            return self.validate_index(int(raw_index), latent_count=latent_count, is_range=is_range, allow_negative=allow_negative)
        except ValueError as e:
            raise ValueError(f"index '{raw_index}' must be an integer.", e)

    def convert_to_latent_keyframes(self, latent_indeces: str, latent_count: int) -> set[LatentKeyframeImport]:
        if not latent_indeces:
            return set()
        all_indeces = [i for i in range(0, latent_count)]
        allow_negative = latent_count > 0
        chosen_indeces = set()
        # parse string - allow positive ints, negative ints, and ranges separated by ':'
        groups = latent_indeces.split(",")
        groups = [g.strip() for g in groups]
        for g in groups:
            # parse strengths - default to 1.0 if no strength given
            strength = 1.0
            if '=' in g:
                g, strength_str = g.split("=", 1)
                g = g.strip()
                try:
                    strength = float(strength_str.strip())
                except ValueError as e:
                    raise ValueError(f"strength '{strength_str}' must be a float.", e)
                if strength < 0:
                    raise ValueError(f"Strength '{strength}' cannot be negative.")
            # parse range of indeces (e.g. 2:16)
            if ':' in g:
                index_range = g.split(":", 1)
                index_range = [r.strip() for r in index_range]
                start_index = self.convert_to_index_int(index_range[0], latent_count=latent_count, is_range=True, allow_negative=allow_negative)
                end_index = self.convert_to_index_int(index_range[1], latent_count=latent_count, is_range=True, allow_negative=allow_negative)
                for i in all_indeces[start_index:end_index]:
                    chosen_indeces.add(LatentKeyframImport(i, strength))
            # parse individual indeces
            else:
                chosen_indeces.add(LatentKeyframeImport(self.convert_to_index_int(g, latent_count=latent_count, allow_negative=allow_negative), strength))
        return chosen_indeces

    def load_keyframes(self,
                       index_strengths: str,
                       prev_latent_keyframe: LatentKeyframeGroupImport=None,
                       latent_image_opt=None):
        if not prev_latent_keyframe:
            prev_latent_keyframe = LatentKeyframeGroupImport()
        curr_latent_keyframe = LatentKeyframeGroupImport()

        latent_count = -1
        if latent_image_opt:
            latent_count = latent_image_opt['samples'].size()[0]
        latent_keyframes = self.convert_to_latent_keyframes(index_strengths, latent_count=latent_count)

        for latent_keyframe in latent_keyframes:
            logger.info(f"keyframe {latent_keyframe.batch_index}:{latent_keyframe.strength}")
            curr_latent_keyframe.add(latent_keyframe)
        
        for latent_keyframe in prev_latent_keyframe.keyframes:
            curr_latent_keyframe.add(latent_keyframe)

        return (curr_latent_keyframe,)

        
class LatentKeyframeInterpolationNodeImport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "batch_index_from": ("INT", {"default": 0, "min": -10000, "max": 10000, "step": 1}),
                "batch_index_to_excl": ("INT", {"default": 0, "min": -10000, "max": 10000, "step": 1}),
                "strength_from": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.0001}, ),
                "strength_to": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.0001}, ),
                "interpolation": (["linear", "ease-in", "ease-out", "ease-in-out"], ),
                "revert_direction_at_midpoint": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "prev_latent_keyframe": ("LATENT_KEYFRAME", ),
            }
        }

    RETURN_TYPES = ("LATENT_KEYFRAME", )
    FUNCTION = "load_keyframe"
    CATEGORY = "Adv-ControlNet 🛂🅐🅒🅝/keyframes"

    def load_keyframe(self,
                        batch_index_from: int,
                        strength_from: float,
                        batch_index_to_excl: int,
                        strength_to: float,
                        interpolation: str,
                        revert_direction_at_midpoint: bool=False,
                        last_key_frame_position: int=0,
                        prev_latent_keyframe: LatentKeyframeGroupImport=None):

        # print value and type
        print(f"batch_index_from: {batch_index_from}")
        print(f"batch_index_to_excl: {batch_index_to_excl}")
        print(f"strength_to: {strength_to}")
        print(f"strength_from: {strength_from}")
        print(f"interpolation: {interpolation}")
        print(f"revert_direction_at_midpoint: {revert_direction_at_midpoint}")
        print(f"prev_latent_keyframe: {prev_latent_keyframe}")
        print(f"last_key_frame_position: {last_key_frame_position}")

        if (batch_index_from > batch_index_to_excl):
            raise ValueError("batch_index_from must be less than or equal to batch_index_to.")

        if (batch_index_from < 0 and batch_index_to_excl >= 0):
            raise ValueError("batch_index_from and batch_index_to must be either both positive or both negative.")
        
        if not prev_latent_keyframe:
            prev_latent_keyframe = LatentKeyframeGroupImport()
        curr_latent_keyframe = LatentKeyframeGroupImport()

        steps = batch_index_to_excl - batch_index_from
        diff = strength_to - strength_from

        index = np.linspace(0, 1, steps // 2 + 1) if revert_direction_at_midpoint else np.linspace(0, 1, steps)

        if interpolation == "linear":
            weights = np.linspace(strength_from, strength_to, len(index))
        elif interpolation == "ease-in":
            weights = diff * np.power(index, 2) + strength_from
        elif interpolation == "ease-out":
            weights = diff * (1 - np.power(1 - index, 2)) + strength_from
        elif interpolation == "ease-in-out":
            weights = diff * ((1 - np.cos(index * np.pi)) / 2) + strength_from

        if revert_direction_at_midpoint:
            weights = np.concatenate([weights, weights[::-1]])

        # Generate frame numbers
        frame_numbers = np.arange(batch_index_from, batch_index_from + len(weights))

        # "Dropper" component: For keyframes with negative start, drop the weights
        if batch_index_from < 0:
            drop_count = abs(batch_index_from)
            weights = weights[drop_count:]
            frame_numbers = frame_numbers[drop_count:]

        # Dropper component: for keyframes a batch_index_to_excl is greater than last_key_frame_position, drop the weights
        if batch_index_to_excl > last_key_frame_position:
            drop_count = batch_index_to_excl - last_key_frame_position
            weights = weights[:-drop_count]
            frame_numbers = frame_numbers[:-drop_count]

        batch_index_from = frame_numbers[0]
        
        for i in range(len(frame_numbers)):
            keyframe = LatentKeyframeImport(batch_index_from + i, float(weights[i]))
            logger.info(f"keyframe {batch_index_from + i}:{weights[i]}")
            curr_latent_keyframe.add(keyframe)

        for latent_keyframe in prev_latent_keyframe.keyframes:
            curr_latent_keyframe.add(latent_keyframe)


        return (curr_latent_keyframe,)


class LatentKeyframeBatchedGroupNodeImport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "strengths": ("FLOAT", {"default": -1, "min": -1, "step": 0.0001}),
            },
            "optional": {
                "prev_latent_keyframe": ("LATENT_KEYFRAME", ),
            }
        }

    RETURN_TYPES = ("LATENT_KEYFRAME", )
    FUNCTION = "load_keyframe"
    CATEGORY = "Adv-ControlNet 🛂🅐🅒🅝/keyframes"

    def load_keyframe(self, strengths: Union[float, list[float]], prev_latent_keyframe: LatentKeyframeGroupImport=None):
        if not prev_latent_keyframe:
            prev_latent_keyframe = LatentKeyframeGroupImport()
        curr_latent_keyframe = LatentKeyframeGroupImport()

        # if received a normal float input, do nothing
        if type(strengths) in (float, int):
            logger.info("No batched strengths passed into Latent Keyframe Batch Group node; will not create any new keyframes.")
        # if iterable, attempt to create LatentKeyframes with chosen strengths
        elif isinstance(strengths, Iterable):
            for idx, strength in enumerate(strengths):
                keyframe = LatentKeyframeImport(idx, strength)
                curr_latent_keyframe.add(keyframe)
                logger.info(f"keyframe {keyframe.batch_index}:{keyframe.strength}")
        else:
            raise ValueError(f"Expected strengths to be an iterable input, but was {type(strengths).__repr__}.")    

        # replace values with prev_latent_keyframes
        for latent_keyframe in prev_latent_keyframe.keyframes:
            curr_latent_keyframe.add(latent_keyframe)

        return (curr_latent_keyframe,)
