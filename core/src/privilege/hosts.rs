use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::Path;

#[cfg(target_os = "macos")]
const HOSTS_PATH: &str = "/etc/hosts";

#[cfg(windows)]
const HOSTS_PATH: &str = r"C:\Windows\System32\drivers\etc\hosts";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HostsEntry {
    pub ip: String,
    pub hostname: String,
    pub aliases: Vec<String>,
}

pub async fn add_hosts_entry(entry: &HostsEntry) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        let content = read_hosts_file()?;
        
        for line in content.lines() {
            if line.contains(&entry.hostname) {
                return Ok(()); // Already exists
            }
        }
        
        // Append to hosts file using sudo
        let line = format!("{}\t{}\t{}\n", entry.ip, entry.hostname, entry.aliases.join(" "));
        append_to_hosts_file(&line).await?;
    }
    
    #[cfg(windows)]
    {
        // Windows implementation
        let content = read_hosts_file()?;
        
        for line in content.lines() {
            if line.contains(&entry.hostname) {
                return Ok(()); // Already exists
            }
        }
        
        // Append to hosts file
        let line = format!("{}\t{}\t{}\r\n", entry.ip, entry.hostname, entry.aliases.join(" "));
        append_to_hosts_file(&line).await?;
    }
    
    Ok(())
}

pub async fn remove_hosts_entry(hostname: &str) -> Result<(), String> {
    let content = read_hosts_file()?;
    let mut new_content = String::new();
    
    for line in content.lines() {
        if !line.contains(hostname) {
            new_content.push_str(line);
            new_content.push('\n');
        }
    }
    
    write_hosts_file(&new_content).await?;
    
    Ok(())
}

fn read_hosts_file() -> Result<String, String> {
    fs::read_to_string(HOSTS_PATH)
        .map_err(|e| format!("Failed to read hosts file: {}", e))
}

#[cfg(target_os = "macos")]
async fn append_to_hosts_file(line: &str) -> Result<(), String> {
    use tokio::process::Command;
    
    Command::new("sudo")
        .args(["sh", "-c", &format!("echo '{}' >> {}", line, HOSTS_PATH)])
        .spawn()
        .map_err(|e| format!("Failed to append to hosts file: {}", e))?;
    
    Ok(())
}

#[cfg(windows)]
async fn append_to_hosts_file(line: &str) -> Result<(), String> {
    use tokio::fs::OpenOptions;
    use tokio::io::AsyncWriteExt;
    
    let mut file = OpenOptions::new()
        .append(true)
        .open(HOSTS_PATH)
        .await
        .map_err(|e| format!("Failed to open hosts file: {}", e))?;
    
    file.write_all(line.as_bytes())
        .await
        .map_err(|e| format!("Failed to write to hosts file: {}", e))?;
    
    file.flush()
        .await
        .map_err(|e| format!("Failed to flush hosts file: {}", e))?;
    
    Ok(())
}

async fn write_hosts_file(content: &str) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        use tokio::process::Command;
        
        Command::new("sudo")
            .args(["sh", "-c", &format!("echo '{}' > {}", content, HOSTS_PATH)])
            .spawn()
            .map_err(|e| format!("Failed to write hosts file: {}", e))?;
    }
    
    #[cfg(windows)]
    {
        use tokio::fs;
        
        fs::write(HOSTS_PATH, content)
            .await
            .map_err(|e| format!("Failed to write hosts file: {}", e))?;
    }
    
    Ok(())
}
