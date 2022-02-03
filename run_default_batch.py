import os
from pathlib import Path
import re
import shutil
import subprocess as sp

input_path = Path('./content/input')
output_path = Path('./content/output')

dain_workdir = Path('./workdir')
dain_workdir.mkdir(exist_ok=True)

frame_batch = 10

def get_first(list, default = None):
    return list[0] if list else default

def get_video_frame_count(
    video_path: Path
) -> int:
    frame_count = sp.getoutput(f" \
        ffprobe \
            -v error \
            -select_streams v:0 \
            -count_frames \
            -show_entries stream=nb_read_frames \
            -print_format default=nokey=1:noprint_wrappers=1 \
            \"{video_path}\" \
    ")
    return int(frame_count)

def get_output_video_fps(
    input_file_path: Path,
    slow_factor: int,
) -> str:
    input_fps_str = sp.getoutput(f" \
        ffprobe \
            -v 0 \
            -of csv=p=0 \
            -select_streams v:0 \
            -show_entries stream=r_frame_rate \"{input_file_path}\" \
    ")

    input_fps_n, input_fps_d = [int(n) for n in input_fps_str.split("/")]
    
    output_fps_n = input_fps_n * slow_factor
    output_fps_d = input_fps_d

    return f"{output_fps_n}/{input_fps_d}"

def get_output_video_path(
    input_file_path: Path,
    output_dir_path: Path,
    slow_factor: int,
    output_fps_str: str,
) -> Path:
    output_fps_n, output_fps_d = [int(n) for n in output_fps_str.split("/")]
    output_fps_int = int(output_fps_n / output_fps_d)
    return output_dir_path / f"{input_file_path.stem}-{slow_factor}x-{output_fps_int}fps.mp4"


def dain_interpolate(
    input_file_path: Path,
    output_file_path: Path,
    interp: int,
    output_fps: str,
):
    print(f"Interpolating {file_path.name} at {interp}x")

    os.system(f" \
        python my_design.py -cli  \
            --input \"{input_file_path}\" \
            --output \"{dain_workdir}\" \
            --interpolations {interp} \
            --half 1 \
            --use_benchmark 0 \
    ")
    
    # we need to correct the framerate and move it to the output folder
    interpolated_video_path = list((dain_workdir / "output_videos").iterdir())[0]
    
    # correct framerate
    os.system(f"ffmpeg -i \"{interpolated_video_path}\" -filter:v fps={output_fps} \"{output_file_path}\"")

# ffmpeg -i content/input/ski_grass-8FPS.mov -vf select="between(n\,10\,20),setpts=PTS-STARTPTS" content/output/test_0002.mp4

for file_path in input_path.iterdir():

    # get iteration count by filename
    # 2x_foobar.mov will interpolate 2x
    interp = int(get_first(re.match("^(\d+(?=x))", file_path.stem), default=8))

    if not interp in [2, 4, 8]:
        interp = 8
       
    output_fps_str = get_output_video_fps(
        input_file_path=file_path,
        slow_factor=interp
    )

    output_video_path = get_output_video_path(
        input_file_path=file_path,
        output_dir_path=output_path,
        slow_factor=interp,
        output_fps_str=output_fps_str,
    )

    if output_video_path.exists():
        print(f"{file_path} already exists! Skipping...")
        continue
    
    # split clip into groups of frames, of size frame_batch

    run_dain(
        input_file_path=file_path,
        output_file_path=output_video_path,
        interp=interp,
        output_fps=output_fps_str,
    )

    # clean up
    shutil.rmtree(dain_workdir, ignore_errors=True)
