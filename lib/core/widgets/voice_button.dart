import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_gradients.dart';
import '../theme/theme_extensions.dart';

class VoiceButton extends StatelessWidget {
  final bool isRecording;
  final VoidCallback onTap;
  final double size;

  const VoiceButton({
    super.key,
    required this.isRecording,
    required this.onTap,
    this.size = 80,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    return GestureDetector(
      onTap: onTap,
      child: SizedBox(
        width: size * 2,
        height: size * 2,
        child: Stack(
          alignment: Alignment.center,
          children: [
            if (isRecording) ...[
              _Ripple(size: size, delay: 0),
              _Ripple(size: size, delay: 0.5),
            ],
            AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              width: size,
              height: size,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: isRecording
                    ? AppGradients.electricPulse
                    : t.primaryGradient,
                boxShadow: [
                  BoxShadow(
                    color: (isRecording
                            ? AppColors.coral500
                            : t.primary)
                        .withValues(alpha: 0.35),
                    blurRadius: 32,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Icon(
                isRecording ? Icons.stop_rounded : Icons.mic_rounded,
                color: t.onPrimary,
                size: size * 0.4,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Ripple extends StatefulWidget {
  final double size;
  final double delay;
  const _Ripple({required this.size, required this.delay});

  @override
  State<_Ripple> createState() => _RippleState();
}

class _RippleState extends State<_Ripple> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );
    Future.delayed(
      Duration(milliseconds: (widget.delay * 1000).toInt()),
      () {
        if (mounted) _ctrl.repeat();
      },
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final scale = 1.0 + _ctrl.value;
        return Opacity(
          opacity: (1.0 - _ctrl.value) * 0.6,
          child: Container(
            width: widget.size * scale,
            height: widget.size * scale,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.coral300, width: 2.5),
            ),
          ),
        );
      },
    );
  }
}
