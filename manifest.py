metadata(
    description="Picovector PPF (pixel) font loader and framebuf renderer.",
    version="0.1.0",
    license="MIT",
)

# ppf_viper holds the optional @micropython.viper blitters. Freezing it is
# fine on any port with a native emitter; ppf imports it behind a guard, so
# ports without one fall back to the portable path at runtime.
module("ppf.py", opt=3)
module("ppf_viper.py", opt=3)
