/* 
This tool is part of the WhiteboxTools geospatial analysis library.
Authors: Dr. John Lindsay
Created: July 13, 2017
Last Modified: July 13, 2017
License: MIT

NOTES: The tool should be updated to take multiple file inputs.
*/
extern crate time;
extern crate num_cpus;

use std::env;
use std::path;
use std::f64;
use raster::*;
use std::io::{Error, ErrorKind};
use std::sync::Arc;
use std::sync::mpsc;
use std::thread;
use tools::WhiteboxTool;

pub struct StandardDeviationContrastStretch {
    name: String,
    description: String,
    parameters: String,
    example_usage: String,
}

impl StandardDeviationContrastStretch {
    pub fn new() -> StandardDeviationContrastStretch { // public constructor
        let name = "StandardDeviationContrastStretch".to_string();
        
        let description = "Performs a standard-deviation contrast stretch on input images.".to_string();
        
        let mut parameters = "-i, --input   Input raster file.\n".to_owned();
        parameters.push_str("-o, --output  Output raster file.\n");
        parameters.push_str("--stdev       Standard deviation clip value (default is 2.0).\n");
        parameters.push_str("--num_tones   Number of tones in the output image (default is 256).\n");
        
        let sep: String = path::MAIN_SEPARATOR.to_string();
        let p = format!("{}", env::current_dir().unwrap().display());
        let e = format!("{}", env::current_exe().unwrap().display());
        let mut short_exe = e.replace(&p, "").replace(".exe", "").replace(".", "").replace(&sep, "");
        if e.contains(".exe") {
            short_exe += ".exe";
        }
        let usage = format!(">>.*{0} -r={1} --wd=\"*path*to*data*\" -i=input.dep -o=output.dep --stdev=2.0 --num_tones=1024", short_exe, name).replace("*", &sep);
    
        StandardDeviationContrastStretch { name: name, description: description, parameters: parameters, example_usage: usage }
    }
}

impl WhiteboxTool for StandardDeviationContrastStretch {
    fn get_tool_name(&self) -> String {
        self.name.clone()
    }

    fn get_tool_description(&self) -> String {
        self.description.clone()
    }

    fn get_tool_parameters(&self) -> String {
        self.parameters.clone()
    }

    fn get_example_usage(&self) -> String {
        self.example_usage.clone()
    }

    fn run<'a>(&self, args: Vec<String>, working_directory: &'a str, verbose: bool) -> Result<(), Error> {
        let mut input_file = String::new();
        let mut output_file = String::new();
        let mut clip_stdev = 2.0;
        let mut num_tones = 256f64;
        
        if args.len() == 0 {
            return Err(Error::new(ErrorKind::InvalidInput,
                                "Tool run with no paramters. Please see help (-h) for parameter descriptions."));
        }
        for i in 0..args.len() {
            let mut arg = args[i].replace("\"", "");
            arg = arg.replace("\'", "");
            let cmd = arg.split("="); // in case an equals sign was used
            let vec = cmd.collect::<Vec<&str>>();
            let mut keyval = false;
            if vec.len() > 1 {
                keyval = true;
            }
            if vec[0].to_lowercase() == "-i" || vec[0].to_lowercase() == "--input" {
                if keyval {
                    input_file = vec[1].to_string();
                } else {
                    input_file = args[i+1].to_string();
                }
            } else if vec[0].to_lowercase() == "-o" || vec[0].to_lowercase() == "--output" {
                if keyval {
                    output_file = vec[1].to_string();
                } else {
                    output_file = args[i+1].to_string();
                }
            } else if vec[0].to_lowercase() == "-stdev" || vec[0].to_lowercase() == "--stdev" {
                if keyval {
                    clip_stdev = vec[1].to_string().parse::<f64>().unwrap();
                } else {
                    clip_stdev = args[i + 1].to_string().parse::<f64>().unwrap();
                }
            } else if vec[0].to_lowercase() == "-num_tones" || vec[0].to_lowercase() == "--num_tones" {
                if keyval {
                    num_tones = vec[1].to_string().parse::<f64>().unwrap();
                } else {
                    num_tones = args[i + 1].to_string().parse::<f64>().unwrap();
                }
            }
        }

        if verbose {
            println!("***************{}", "*".repeat(self.get_tool_name().len()));
            println!("* Welcome to {} *", self.get_tool_name());
            println!("***************{}", "*".repeat(self.get_tool_name().len()));
        }

        let sep: String = path::MAIN_SEPARATOR.to_string();

        let mut progress: usize;
        let mut old_progress: usize = 1;

        if !input_file.contains(&sep) {
            input_file = format!("{}{}", working_directory, input_file);
        }
        if !output_file.contains(&sep) {
            output_file = format!("{}{}", working_directory, output_file);
        }

        if verbose { println!("Reading input data...") };
        let input = Arc::new(Raster::new(&input_file, "r")?);
        let rows = input.configs.rows as isize;
        let columns = input.configs.columns as isize;
        let nodata = input.configs.nodata;

        if input.configs.data_type == DataType::RGB24 ||
            input.configs.data_type == DataType::RGB48 ||
            input.configs.data_type == DataType::RGBA32 {

            return Err(Error::new(ErrorKind::InvalidInput,
                "This tool is intended to be applied to single-band greyscale rasters and not RGB colour-composite images."));
        }
        
        let start = time::now();

        if verbose { println!("Calculating clip values...") };
        let (mean, stdev) = input.calculate_mean_and_stdev();
        let min_val = mean - stdev * clip_stdev;
        let max_val = mean + stdev * clip_stdev;
        let value_range = max_val - min_val;
        if value_range < 0f64 {
            return Err(Error::new(ErrorKind::InvalidInput,
                                "The calculated clip values are incorrect."));
        }
        
        let num_procs = num_cpus::get() as isize;
        let (tx, rx) = mpsc::channel();
        for tid in 0..num_procs {
            let input = input.clone();
            let tx = tx.clone();
            thread::spawn(move || {
                let mut z_in: f64;
                let mut z_out: f64;
                for row in (0..rows).filter(|r| r % num_procs == tid) {
                    let mut data: Vec<f64> = vec![nodata; columns as usize];
                    for col in 0..columns {
                        z_in = input[(row, col)];
                        if z_in != nodata {
                            z_out = ((z_in - min_val) / value_range * num_tones).floor();
                            if z_out < 0f64 { z_out = 0f64; }
                            if z_out >= num_tones { z_out = num_tones - 1f64; }
                            data[col as usize] = z_out;
                        }
                    }
                    tx.send((row, data)).unwrap();
                }
            });
        }

        let mut output = Raster::initialize_using_file(&output_file, &input);
        for r in 0..rows {
            let (row, data) = rx.recv().unwrap();
            output.set_row_data(row, data);
            if verbose {
                progress = (100.0_f64 * r as f64 / (rows - 1) as f64) as usize;
                if progress != old_progress {
                    println!("Progress: {}%", progress);
                    old_progress = progress;
                }
            }
        }

        let end = time::now();
        let elapsed_time = end - start;
        output.add_metadata_entry(format!("Created by whitebox_tools\' {} tool", self.get_tool_name()));
        output.add_metadata_entry(format!("Input file: {}", input_file));
        output.add_metadata_entry(format!("Standard deviation clip value: {}", clip_stdev));
        output.add_metadata_entry(format!("Calculated lower-tail clip value: {}", min_val));
        output.add_metadata_entry(format!("Calculated upper-tail clip value: {}", max_val));
        output.add_metadata_entry(format!("Number of tones: {}", num_tones));
        output.add_metadata_entry(format!("Elapsed Time (excluding I/O): {}", elapsed_time).replace("PT", ""));

        if verbose { println!("Saving data...") };
        let _ = match output.write() {
            Ok(_) => if verbose { println!("Output file written") },
            Err(e) => return Err(e),
        };

        println!("{}", &format!("Elapsed Time (excluding I/O): {}", elapsed_time).replace("PT", ""));

        Ok(())
    }
}