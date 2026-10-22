"""Generate a 5-minute spoken lecture audio file using Windows speech synthesis for benchmarking."""

import os
import subprocess
from pathlib import Path

LECTURE_SCRIPT = """
Welcome class. Today we will delve into thermodynamics, energy conservation, and heat engine cycles.

Let us begin with the First Law of Thermodynamics for a closed system. The First Law states that the change in internal energy, delta U, is equal to the net heat added to the system, Q, minus the net work done by the system on its surroundings, W. Mathematically, delta U equals Q minus W.

It is critical to understand the distinction between state variables and path functions. Internal energy U, pressure P, and temperature T are state properties. They depend exclusively on the thermodynamic state of equilibrium. Whether an ideal gas reaches a pressure of two atmospheres via an isothermal path or an adiabatic path, its internal energy at that final temperature is identical. Therefore, the cyclic integral of any state property, such as delta U or entropy delta S, is strictly zero.

In stark contrast, heat Q and work W are path functions. They represent energy in transit across system boundaries. The cyclic integral of work does not vanish, which is precisely why heat engines can produce continuous net positive work output over closed cycles.

Now let us examine quasi-static boundary work. When a gas expands against a movable piston, the work performed is given by the integral of pressure P with respect to volume dV. In an isobaric process, where pressure remains constant at P, the work done simplifies to P multiplied by the change in volume, V2 minus V1.

Let us solve a practical numerical problem. Suppose an ideal gas expands in a piston-cylinder apparatus from an initial volume of 0.04 cubic meters to a final volume of 0.10 cubic meters against a constant pressure of 1.5 times 10 to the power of 5 Pascals. During this expansion, 12,000 Joules of heat is transferred into the gas.

Our given data is: Pressure P equals 1.5 times 10 to the 5 Pascals. Initial volume V1 is 0.04 cubic meters. Final volume V2 is 0.10 cubic meters. Heat added Q is 12,000 Joules.
We need to find the work done W and the change in internal energy delta U.

Step one: Calculate boundary work. W equals P times delta V, which is 1.5 times 10 to the 5 multiplied by 0.10 minus 0.04, yielding 1.5 times 10 to the 5 times 0.06. This gives exactly 9,000 Joules of work done by the gas.
Step two: Apply the First Law. Delta U equals Q minus W, which is 12,000 Joules minus 9,000 Joules, resulting in a change in internal energy of 3,000 Joules.
Our final answer is: Work done equals 9,000 Joules, and internal energy increase equals 3,000 Joules. Notice that 75 percent of the heat was converted into boundary work, while 25 percent raised the gas temperature.

Next, we turn to the Second Law of Thermodynamics and the Carnot cycle. Formulated by Sadi Carnot, the Carnot cycle establishes the theoretical upper ceiling for any heat engine operating between two thermal reservoirs: a hot reservoir at absolute temperature T sub H, and a cold reservoir at absolute temperature T sub C.

The cycle consists of four reversible stages: First, isothermal expansion at T sub H where heat Q sub H is absorbed. Second, adiabatic expansion where the gas cools down to T sub C without heat transfer. Third, isothermal compression at T sub C where waste heat Q sub C is rejected. Fourth, adiabatic compression returning the gas to T sub H.

The thermal efficiency eta of a Carnot cycle is given by 1 minus T sub C divided by T sub H. Remember, temperatures must always be expressed in Kelvin. For example, if a furnace operates at 600 degrees Celsius, its absolute temperature T sub H is 873.15 Kelvin. If the cooling water is at 25 degrees Celsius, T sub C is 298.15 Kelvin.
The Carnot efficiency is 1 minus 298.15 over 873.15, which yields approximately 65.85 percent. No real physical heat engine operating between these limits can ever exceed 65.85 percent efficiency due to irreversibilities and entropy generation.

In summary, remember the sign conventions, remember that state functions are path-independent, and always convert temperatures to Kelvin when computing thermal efficiencies. Thank you for your attention.
"""


def generate_lecture_audio(output_wav: Path):
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    temp_txt = output_wav.with_suffix(".txt")
    temp_txt.write_text(LECTURE_SCRIPT, encoding="utf-8")

    ps_script = f"""
    Add-Type -AssemblyName System.Speech
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.Rate = 0
    $synth.SetOutputToWaveFile('{output_wav.resolve()}')
    $text = Get-Content -Path '{temp_txt.resolve()}' -Raw
    $synth.Speak($text)
    $synth.Dispose()
    """
    
    print(f"Generating realistic spoken lecture audio at: {output_wav}...")
    subprocess.run(["powershell", "-Command", ps_script], check=True)
    size_mb = output_wav.stat().st_size / (1024 * 1024)
    print(f"Audio generated successfully: {size_mb:.2f} MB")


if __name__ == "__main__":
    tests_dir = Path(__file__).resolve().parent.parent / "tests"
    wav_path = tests_dir / "sample_5min_lecture.wav"
    generate_lecture_audio(wav_path)
