import os
from pathlib import Path
import re
import shutil
import subprocess as sp

input_path = Path('./content/input')
output_path = Path('./content/output')

dain_workdir = Path('./workdir')
dain_workdir.mkdir(exist_ok=True)

frame_batch_size = 30

def get_first(list, default = None):
    return list[0] if list else default

def is_video(
    video_path: Path
) -> bool:
    res = sp.getoutput(f" \
        ffprobe \
            -loglevel error \
            -select_streams v \
            -show_entries stream=codec_type \
            -of csv=p=0 \
            \"{video_path}\" \
    ")

    return res == "video"

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

def get_video_fps(video_path: Path) -> str:
    return sp.getoutput(f" \
        ffprobe -v 0 \
            -of csv=p=0 \
            -select_streams v:0 \
            -show_entries stream=r_frame_rate \
        \"{video_path}\" \
    ")

def get_output_video_fps(
    input_file_path: Path,
    slow_factor: int,
) -> str:
    input_fps_str = get_video_fps(input_file_path)
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

def run_dain(
    input_file_path: Path,
    output_file_path: Path,
    interp: int,
    output_fps: str,
):
    print(f"Interpolating {file_path.name} at {interp}x")
    
    shutil.rmtree(dain_workdir, ignore_errors=True)

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
    if not is_video(file_path):
        print(f"Skipping non-video file: {file_path}")
        continue

    input_video_path = file_path

    # get iteration count by filename
    # 2x_foobar.mov will interpolate 2x
    interp = int(get_first(re.match("^(\d+(?=x))", file_path.stem), default=4))

    if not interp in [2, 4, 8]:
        interp = 8
       
    output_fps_str = get_output_video_fps(
        input_file_path=input_video_path,
        slow_factor=interp
    )

    output_video_path = get_output_video_path(
        input_file_path=input_video_path,
        output_dir_path=output_path,
        slow_factor=interp,
        output_fps_str=output_fps_str,
    )

    if output_video_path.exists():
        print(f"{input_video_path} already exists! Skipping...")
        continue
    
    frame_count = get_video_frame_count(input_video_path)
    # splitting video into smaller batches improves stability and reduces crashes
    if frame_count > frame_batch_size:
        # set up directories
        tmp_work_dir = output_path / input_video_path.stem
        tmp_videos_path = tmp_work_dir / "video-segments"
        tmp_concat_path = tmp_work_dir / "videos-to-concat"

        # create them if necessary
        tmp_work_dir.mkdir(parents=True, exist_ok=True)
        tmp_videos_path.mkdir(parents=True, exist_ok=True)
        tmp_concat_path.mkdir(parents=True, exist_ok=True)

        concat_video_paths = []

        # extract videos
        for i in range(0, frame_count // frame_batch_size + 1):
            segment_video_path = tmp_videos_path / f"{i:05d}-{output_video_path.name}"
            dain_seg_video_path = tmp_videos_path / f"dain-{segment_video_path.name}"
            to_concat_video_path = tmp_concat_path / segment_video_path.name

            # extract a video segment starting from frame i * frame_batch_size, ending at frame (i + 1) * frame_batch_size
            if not segment_video_path.exists():
                input_video_fps = get_video_fps(input_video_path)
                frame_start = i * frame_batch_size
                frame_stop = min(frame_count - 1, (i + 1) * frame_batch_size)
                os.system(f" \
                    ffmpeg \
                        -i \"{input_video_path}\" \
                        -r \"{input_video_fps}\" \
                        -vsync vfr \
                        -vf \"\
                            select=between(n\,{frame_start}\,{frame_stop}), \
                            setpts=PTS-STARTPTS \
                        \" \
                        \"{segment_video_path}\" \
                ")

            # run dain on the video segment
            if not dain_seg_video_path.exists():
                run_dain(
                    input_file_path=segment_video_path,
                    output_file_path=dain_seg_video_path,
                    interp=interp,
                    output_fps=output_fps_str,
                )

            # cut off first frame and re-export
            if not to_concat_video_path.exists():
                if i == 0:
                    shutil.copy(dain_seg_video_path, to_concat_video_path)
                else:
                    os.system(f" \
                        ffmpeg \
                            -i \"{dain_seg_video_path}\" \
                            -vf \"select=gte(n\,{interp})\" \
                            \"{to_concat_video_path}\" \
                        ")

            concat_video_paths.append(to_concat_video_path)
            
            # end extract videos loop

        # concat videos
        concat_file_path = tmp_work_dir / "concat.txt"
        concat_file = open(concat_file_path, "w")
        concat_file.write("\n".join([f"file '{path.relative_to(tmp_work_dir)}'" for path in concat_video_paths]))
        concat_file.close()

        os.system(f" \
            ffmpeg \
                -f concat \
                -r {output_fps_str} \
                -safe 0 \
                -i \"{concat_file_path}\" \
                -c copy \
                \"{output_video_path}\" \
        ")

        exit()
        # nuke tmp dir
        shutil.rmtree(tmp_work_dir, ignore_errors=True)

    else:
        run_dain(
            input_file_path=input_video_path,
            output_file_path=output_video_path,
            interp=interp,
            output_fps=output_fps_str,
        )

    # clean up
    shutil.rmtree(dain_workdir, ignore_errors=True)
