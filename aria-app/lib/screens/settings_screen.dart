import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/aria_channel.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final TextEditingController _apiKeyController = TextEditingController();
  bool _wakeWordEnabled = true;
  bool _voiceResponseEnabled = true;
  bool _apiKeySaved = false;
  bool _isObscured = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _apiKeyController.text = prefs.getString('claude_api_key') ?? '';
      _wakeWordEnabled = prefs.getBool('wake_word_enabled') ?? true;
      _voiceResponseEnabled = prefs.getBool('voice_response_enabled') ?? true;
    });
  }

  Future<void> _saveApiKey() async {
    final key = _apiKeyController.text.trim();
    if (key.isEmpty) {
      _showSnack('Please enter an API key');
      return;
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('claude_api_key', key);
    setState(() => _apiKeySaved = true);
    _showSnack('API key saved ✓');
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _apiKeySaved = false);
    });
  }

  Future<void> _saveToggle(String key, bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(key, value);
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: const Color(0xFF111118),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  @override
  void dispose() {
    _apiKeyController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ─── API Key Section ─────────────────────────────────────────────
          _SectionHeader(title: 'Claude API'),

          _SettingsCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'API Key',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: Colors.white70,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Get your key at console.anthropic.com',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: Colors.white38,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _apiKeyController,
                  obscureText: _isObscured,
                  style: const TextStyle(
                    color: Colors.white,
                    fontFamily: 'monospace',
                    fontSize: 13,
                  ),
                  decoration: InputDecoration(
                    hintText: 'sk-ant-...',
                    suffixIcon: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          icon: Icon(
                            _isObscured
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
                            size: 18,
                          ),
                          color: Colors.white38,
                          onPressed: () =>
                              setState(() => _isObscured = !_isObscured),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _apiKeySaved
                          ? Colors.green.shade800
                          : const Color(0xFF00d4ff),
                      foregroundColor:
                          _apiKeySaved ? Colors.white : Colors.black,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: _saveApiKey,
                    child: Text(_apiKeySaved ? '✓ Saved' : 'Save API Key'),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ─── Voice Section ───────────────────────────────────────────────
          _SectionHeader(title: 'Voice'),

          _SettingsCard(
            child: Column(
              children: [
                _ToggleTile(
                  title: 'Wake Word',
                  subtitle: 'Say "Hey Aria" to activate',
                  icon: Icons.mic_rounded,
                  value: _wakeWordEnabled,
                  onChanged: (value) {
                    setState(() => _wakeWordEnabled = value);
                    _saveToggle('wake_word_enabled', value);
                  },
                ),
                const Divider(height: 1, color: Color(0xFF1E1E28)),
                _ToggleTile(
                  title: 'Voice Responses',
                  subtitle: 'Aria speaks replies aloud',
                  icon: Icons.volume_up_rounded,
                  value: _voiceResponseEnabled,
                  onChanged: (value) {
                    setState(() => _voiceResponseEnabled = value);
                    _saveToggle('voice_response_enabled', value);
                  },
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ─── Accessibility Section ───────────────────────────────────────
          _SectionHeader(title: 'Accessibility'),

          _SettingsCard(
            child: _ActionTile(
              title: 'Enable Accessibility Service',
              subtitle: 'Required for screen reading & gestures',
              icon: Icons.accessibility_new_rounded,
              onTap: () {
                AriaChannel.openAccessibilitySettings();
              },
              trailing: const Icon(
                Icons.open_in_new_rounded,
                size: 16,
                color: Colors.white38,
              ),
            ),
          ),

          const SizedBox(height: 16),

          // ─── About Section ───────────────────────────────────────────────
          _SectionHeader(title: 'About'),

          _SettingsCard(
            child: Column(
              children: [
                _InfoTile(label: 'Version', value: '0.1.0'),
                const Divider(height: 1, color: Color(0xFF1E1E28)),
                _InfoTile(label: 'Model', value: 'claude-3-5-haiku-20241022'),
                const Divider(height: 1, color: Color(0xFF1E1E28)),
                _InfoTile(label: 'Tools', value: '12 native Android tools'),
              ],
            ),
          ),

          const SizedBox(height: 32),
        ],
      ),
    );
  }
}

// ─── Sub-widgets ─────────────────────────────────────────────────────────────

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8, top: 4),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          color: Color(0xFF00d4ff),
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.5,
        ),
      ),
    );
  }
}

class _SettingsCard extends StatelessWidget {
  final Widget child;
  const _SettingsCard({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF111118),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
      ),
      padding: const EdgeInsets.all(16),
      child: child,
    );
  }
}

class _ToggleTile extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _ToggleTile({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF00d4ff), size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(color: Colors.white, fontSize: 15)),
                Text(subtitle,
                    style: const TextStyle(
                        color: Colors.white38, fontSize: 12)),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: const Color(0xFF00d4ff),
          ),
        ],
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;
  final Widget? trailing;

  const _ActionTile({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF00d4ff), size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(color: Colors.white, fontSize: 15)),
                Text(subtitle,
                    style: const TextStyle(
                        color: Colors.white38, fontSize: 12)),
              ],
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final String label;
  final String value;

  const _InfoTile({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: const TextStyle(color: Colors.white54, fontSize: 14)),
          Text(value,
              style: const TextStyle(color: Colors.white70, fontSize: 14)),
        ],
      ),
    );
  }
}
