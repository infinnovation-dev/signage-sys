#=======================================================================
#       Digital signage image
#=======================================================================

def build(g, cfg):
    g.from_named('pisys-pwmin')
    g.env('DEBIAN_FRONTEND','noninteractive')

    user = cfg.get('user',{})
    username = user.get('name','pi')
    home = '/home/%s' % username

    #g.run('apt-get update')
    #g.run('apt-get dist-upgrade -y')

    # Pre-requisites for piwall binaries
    g.install('libgd3',         # Pulls in lots of X stuff :-(
              'libglib2.0-0')
    # Python for libreoffice control
    python = cfg.get('python',{}).get('version','python')
    g.install(python)
    # Run X server as user pi, not root
    g.copy_as_helper('nodm.dc')
    g.run('debconf-set-selections', stdin='/helpers/nodm.dc')
    g.install('xserver-xorg-video-fbdev',
              'nodm',        # Display manager suitable for kiosk use
              'matchbox',    # Window manager
              'libreoffice-impress')
    #g.run("sed -i -e 's/^NODM_USER=.*/NODM_USER=pi/' /etc/default/nodm")
    # Ensure NTP servers used by systemd-timesyncd
    # See https://www.raspberrypi.org/forums/viewtopic.php?t=217832
    g.copy_file('50-timesyncd.conf',
                '/lib/dhcpcd/dhcpcd-hooks/')

    # xset, xmodmap, xrdb etc. (pulls in cpp)
    g.install('x11-xserver-utils')
    # Keyboard & mouse input
    g.install('xserver-xorg-input-evdev',
              'dbus')        # Else error every 10s
    # For communicating with libreoffice (no python2 equivalent)
    g.install('python3-uno')
    # Pre-requisites for CCFE::Authen
    g.install('libnet-dns-perl',
              'libcrypt-dh-perl',
              'libipc-shareable-perl')
    # Fonts for MS Office compatibility
    # - needs certificates to trust sourceforge hosts
    g.install('ca-certificates')
    g.install('ttf-mscorefonts-installer')
    # Other pre-requisites
    python = cfg.get('python',{}).get('version','python')
    g.install('cec-utils',   # Control TV on/off etc
              python+'-bottle', # Web framework
              'dma',            # Mail agent
              'heirloom-mailx', # Mail client
              'watchdog',       # Ensure apps keep running
              )
    g.mkdir('/data/signage')
    g.run(['chown','--reference='+home, '/data/signage'])
    g.mkdir('/data/log')
    g.mkdir('/data/tmp')
    g.run('chmod ugo+rwx,o+t /data/tmp')
    #g.put('USER pi:pi')
    #g.WORKDIR('/home/pi')
    for item in ('bin','rc.pi','.xsession'):
        g.symlink('ccfe-signage/%s' % item, '%s/%s' % (home,item))
        g.run(['chown','--reference='+home,'--no-dereference',
               '%s/%s' % (home,item)])
    g.symlink('/tmp/libreoffice-pi','%s/libreoffice' % home)
    g.run(['chown','--reference='+home,'--no-dereference', '%s/libreoffice' % home])
    g.symlink('/data/log/cec.log', '%s/cec.log' % home)
    g.run(['chown','--reference='+home,'--no-dereference', '%s/cec.log' % home])
    
    for app in ('clock','ticker','web'):
        g.symlink('/home/pi/ccfe-signage/signage-%s.service' % app,
                  '/etc/systemd/system/')
        g.symlink('/home/pi/ccfe-signage/signage-%s.service' % app,
                  '/etc/systemd/system/multi-user.target.wants/signage-%s.service' % app)
    # Cron jobs
    g.write_lines('/etc/cron.d/signage',
                  '# Show newest presentation',
                  '2 1 * * *  pi  /home/pi/bin/signage-nightly')
    # Stock pi-gen leaves partitions unassigned.  Firm them up now.
    g.run('sed -i -e s#ROOTDEV#/dev/mmcblk0p2# /boot/cmdline.txt') 
    g.run('sed -i -e s#BOOTDEV#/dev/mmcblk0p1# -e s#ROOTDEV#/dev/mmcblk0p2# /etc/fstab')
    # Set UK timezone
    g.write_lines('/etc/timezone', 'Europe/London')
    g.run('rm /etc/localtime')
    g.run('dpkg-reconfigure -f noninteractive tzdata')
    # Mail handling
    mail = cfg.get('mail',{})
    mta = mail.get('mta')
    smarthost = mail.get('smarthost')
    #if smarthost == 'DHCP':
    #    # Get SMTP smarthost from DHCP
    #    g.run('echo "option smtp_server" >> /etc/dhcpcd.conf')
    if smarthost and smarthost != 'DHCP':
        if mta == 'dma':
            g.run('echo "SMARTHOST %s" > /etc/dma/dma.conf' % smarthost)

    user_auth(g, cfg)
    make_readonly(g, cfg)

    data = cfg.get('data', {})
    dev = data.get('dev')
    if dev:
        if dev == 'local':
            dev = '/dev/mmcblk0p3'
        g.append_lines('/etc/fstab',
                       '%-15s /data          ext4    defaults,noatime  0       2' % dev)

    extra = cfg.get('config',[])
    if extra:
        g.append_lines('/boot/config.txt', *extra)


def user_auth(g, cfg):
    """Set up authorization for logging on"""
    user = cfg.get('user',{})
    username = user.get('name','pi')
    # Set password access
    usercryptpw = user.get('cryptpw')
    if usercryptpw is not None:
        g.run("echo '%s:%s' | chpasswd -e" % (username, usercryptpw))
    # Set up ssh keys
    home = '/home/%s' % username
    sshdir = home + '/.ssh'
    g.mkdir(sshdir, mode='700')
    g.run(['chown','--reference='+home, sshdir])
    keys = user.get('authkeys',[])
    if keys:
        keyfile = sshdir + '/authorized_keys'
        g.write_lines(keyfile, *keys)
        g.run(['chmod','644', keyfile])
        g.run(['chown','--reference='+home, keyfile])

def make_readonly(g, cfg, opts=()):
    readonly = cfg.get('readonly')
    if readonly:
        #--- Common for any technique
        # systemd tries to set this and complains if it can't
        g.symlink('../proc/self/mounts','/etc/mtab')
        # similarly
        g.mkdir('/var/lib/systemd/coredump', mode='755')
        # /usr/lib/tmpfiles.d/sudo.conf tries to create timestamp dir etc.
        g.symlink('/dev/null','/etc/tmpfiles.d/sudo.conf')
        # resolver configuration moved to /run (N.B. temp location for docker)
        g.symlink('../run/resolv.conf','/var/local/resolv.conf')
        # dragonfly mail agent moved to /run
        if 'dma' in opts:
            g.symlink('../../run/dma.conf','/etc/dma/dma.conf')
        g.copy_file('piro',
                    '/usr/bin/',
                    mode='755')
        g.copy_file('piro-dhcp',
                    '/sbin/',
                    mode='755')
        g.run('rm -f /etc/systemd/system/dhcpcd.service.d/wait.conf')
        g.copy_file('piro-systemd-dhcpcd.conf',
                    '/etc/systemd/system/dhcpcd.service.d/piro.conf')
        # Files which dhcpcd tries to write
        for item in ('dhcpcd.uid','dhcpcd.secret'):
            g.symlink('../run/%s' % item, '/etc/%s' % item)
        g.run('rmdir /var/lib/dhcpcd5')
        g.symlink('../../run/dhcpcd5','/var/lib/dhcpcd5')
        g.copy_file('e2fsck.conf',
                    '/etc/')
        # Disable regular jobs, typically updates and backups
        g.run('systemctl disable apt-daily.timer')
        g.run('systemctl disable apt-daily-upgrade.timer')
        jobs = (('dpkg','daily'),
                ('man-db','daily'), ('man-db','weekly'),
                ('passwd','daily'),
                ('fake-hwclock','hourly'))
        for job, freq in jobs:
            script = '/etc/cron.%s/%s' % (freq, job)
            g.run(['dpkg-divert','--add','--rename','--divert',
                   script+'.disabled', script])
    # Specifics for read-only techniques
    if readonly == 'root-ro':
        # Read-only root as per https://gist.github.com/kidapu/a03dd5bb8f4ac6a4c7e69c28bacde1d3
        g.copy_file('root-ro',
                  '/etc/initramfs-tools/scripts/init-bottom/',
                  mode='755')
        g.append_lines('/etc/initramfs-tools/modules', 'overlay')
        g.run('mkinitramfs -o /boot/initrd /lib/modules/*v7*')
    elif readonly == 'piro':
        # Techniques as used in piwall/piro, adapted for systemd etc
        for fs,size in (('/tmp','20%'),('/var/tmp','5%'),('/var/log','10%')):
            g.append_lines('/etc/fstab',
                           'tmpfs           %-15s tmpfs   noatime,nodev,noexec,size=%s,mode=1777 0 0' % (fs,size))
        g.copy_file('piro-tmpfiles.conf',
                    '/etc/tmpfiles.d')
        if 'dma' in opts:
            g.run('rm -fr /var/spool/dma')
            g.symlink('/run/dma-spool','/var/spool/dma')
        #for mtpt in ('boot','-'):
        #    d.copy_install('helpers/piro-mount.conf',
        #                   '/etc/systemd/system/%s.mount.d/' % mtpt)
        #d.copy_install('helpers/50piro_xsessionerrors',
        #              '/etc/X11/Xsession.d')
        # Set /boot and / read-only
        g.run('sed -i -e "/mmcblk0p[12]/s/defaults/defaults,ro/" /etc/fstab')
    elif readonly is not None:
        raise ValueError('Unknown readonly scheme %r' % readonly)

    g.finish()
